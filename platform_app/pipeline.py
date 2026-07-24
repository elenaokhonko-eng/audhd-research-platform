import json
import re
import httpx
from pathlib import Path
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from platform_app.models import Approval, Artifact, LiteratureChunk, LiteratureDocument, ResearchRun, SourceClaim
from platform_app.repository import ResearchRunRepository
from platform_app.services.agents import run_agent_stage
from platform_app.services.artifacts import Citation, render_scientific_pdf
from platform_app.services.documents import TextPassage, chunk_passages, download_open_access_document, parse_downloaded_document
from platform_app.services.literature import CrossrefConnector, OpenAlexConnector, PubMedConnector, merge_works
from platform_app.services.publishing import ManualSubstackAdapter, build_publication_package
from platform_app.services.rag import EmbeddingProvider
from platform_app.services.storage import ArtifactStorage
from platform_app.services.verification import ClaimVerifier
from platform_app.settings import Settings
from platform_app.workflow import WorkflowStage


class PipelineRunner:
    def __init__(self, session: Session, settings: Settings):
        self.session = session
        self.settings = settings
        self.repository = ResearchRunRepository(session)
        self.storage = ArtifactStorage(settings)

    def execute_current_stage(self, run_id: UUID, actor: str = "worker") -> dict:
        run = self.repository.get(run_id, lock=True)
        if not run:
            raise KeyError(run_id)
        stage = WorkflowStage(run.stage)
        handlers = {
            WorkflowStage.SUBMITTED: self._start,
            WorkflowStage.FORMALIZING: self._formalize,
            WorkflowStage.RETRIEVING: self._retrieve,
            WorkflowStage.SYNTHESIZING: self._synthesize,
            WorkflowStage.REPORTING: self._report,
            WorkflowStage.PDF_QA: self._pdf,
            WorkflowStage.ADAPTING: self._substack,
            WorkflowStage.VISUALS: self._visuals,
            WorkflowStage.DRAFTING: self._draft,
            WorkflowStage.PUBLISHING: self._publish,
        }
        if stage not in handlers:
            return {"run_id": str(run_id), "stage": stage.value, "status": "waiting"}
        target, details = handlers[stage](run)
        advanced = self.repository.advance(run_id, target, actor)
        return {"run_id": str(run_id), "stage": advanced.stage, "status": "completed", **details}

    def _put_artifact(self, run: ResearchRun, kind: str, content: bytes, content_type: str) -> Artifact:
        self.storage.ensure_bucket()
        key = f"runs/{run.id}/v{run.version}/{kind}"
        stored = self.storage.put(key, content, content_type, {"run-id": str(run.id), "kind": kind})
        existing = self.session.scalar(select(Artifact).where(Artifact.object_key == stored.key))
        if existing:
            existing.sha256 = stored.sha256
            existing.metadata_json = {"size": stored.size, "content_type": content_type}
            self.session.flush()
            return existing
        artifact = Artifact(run_id=run.id, kind=kind, object_key=stored.key, sha256=stored.sha256, metadata_json={"size": stored.size, "content_type": content_type})
        self.session.add(artifact)
        self.session.flush()
        return artifact

    def _latest_text(self, run: ResearchRun, kind: str) -> str:
        artifact = self._latest_artifact(run, kind)
        if not artifact:
            raise RuntimeError(f"Required artifact is missing: {kind}")
        return self.storage.get(artifact.object_key).decode("utf-8")

    def _latest_artifact(self, run: ResearchRun, kind: str) -> Artifact | None:
        return self.session.scalar(select(Artifact).where(Artifact.run_id == run.id, Artifact.kind == kind).order_by(Artifact.created_at.desc()).limit(1))

    def _start(self, run: ResearchRun):
        return WorkflowStage.FORMALIZING, {}

    def _formalize(self, run: ResearchRun):
        output = run_agent_stage("formalize", f"Formalize this hypothesis:\n\n{run.hypothesis}\n\nReturn constructs, operational variables, H0, H1, confounders, falsifiability, ethics, and clarification questions.", "A structured Markdown hypothesis protocol for human review.")
        artifact = self._put_artifact(run, "formalized_hypothesis.md", output.encode(), "text/markdown")
        return WorkflowStage.HYPOTHESIS_REVIEW, {"artifact_id": str(artifact.id)}

    def _retrieve(self, run: ResearchRun):
        clients = [
            PubMedConnector(api_key=self.settings.ncbi_api_key, mailto=self.settings.research_contact_email),
            CrossrefConnector(mailto=self.settings.research_contact_email),
            OpenAlexConnector(api_key=self.settings.openalex_api_key, mailto=self.settings.research_contact_email),
        ]
        crossref = clients[1]
        try:
            works = merge_works(*(client.search(run.hypothesis, limit=25) for client in clients))
            verified_dois = {work.doi for work in works if work.doi and crossref.resolve_doi(work.doi)}
        finally:
            for client in clients:
                client.close()
        embedder = EmbeddingProvider(self.settings) if self.settings.embedding_api_key else None
        stored = 0
        full_text_downloads = 0
        for work in works:
            document = self.session.scalar(select(LiteratureDocument).where(LiteratureDocument.doi == work.doi)) if work.doi else None
            if not document:
                document = LiteratureDocument(title=work.title, doi=work.doi, source_url=work.source_url or "", publication_year=work.publication_year, provenance={"provider": work.source, "external_id": work.external_id, "authors": work.authors, "is_retracted": work.is_retracted}, rights={"full_text_url": work.full_text_url}, verified=bool(work.doi in verified_dois and not work.is_retracted))
                self.session.add(document)
                self.session.flush()
            passages = []
            extraction_source = "abstract"
            if work.full_text_url and full_text_downloads < 10:
                try:
                    downloaded = download_open_access_document(work.full_text_url, self.settings.max_full_text_bytes)
                    passages = chunk_passages(parse_downloaded_document(downloaded))
                    self._put_artifact(run, f"sources/{document.id}", downloaded.content, downloaded.content_type)
                    extraction_source = "open_access_full_text"
                    document.rights = {**document.rights, "downloaded_from": downloaded.final_url, "access_basis": "provider-declared-open-access"}
                    full_text_downloads += 1
                except (ValueError, httpx.HTTPError):
                    passages = []
            if not passages and work.abstract:
                passages = chunk_passages([TextPassage(work.abstract)])
            if passages:
                vectors = embedder.embed([item.text for item in passages]) if embedder else [None] * len(passages)
                for passage, vector in zip(passages, vectors):
                    self.session.add(LiteratureChunk(document_id=document.id, text=passage.text, page_start=passage.page_start, page_end=passage.page_end, embedding=vector, extraction_metadata={"source": extraction_source}))
            stored += 1
        self.session.flush()
        return WorkflowStage.SYNTHESIZING, {"sources": stored}

    def _evidence_rows(self, limit: int = 80):
        return self.session.execute(select(LiteratureChunk, LiteratureDocument).join(LiteratureDocument).where(LiteratureDocument.verified.is_(True)).limit(limit)).all()

    def _evidence_context(self, run: ResearchRun, limit: int = 80) -> str:
        rows = self._evidence_rows(limit)
        return "\n\n".join(f"[E{index}] {document.title} | DOI: {document.doi or 'none'}\n{chunk.text}" for index, (chunk, document) in enumerate(rows, 1))

    def _synthesize(self, run: ResearchRun):
        evidence = self._evidence_context(run)
        output = run_agent_stage("synthesis", f"Research hypothesis:\n{run.hypothesis}\n\nEvidence passages:\n{evidence}\n\nUse only these passages. Cite every factual claim with [E#]. Flag conflicts, missing evidence, and unverifiable statements.", "A citation-linked evidence synthesis in Markdown.")
        artifact = self._put_artifact(run, "evidence_synthesis.md", output.encode(), "text/markdown")
        rows = self._evidence_rows()
        crossref = CrossrefConnector(mailto=self.settings.research_contact_email)
        verifier = ClaimVerifier(crossref)
        audit = []
        try:
            for sentence in re.split(r"(?<=[.!?])\s+", output):
                for reference in {int(value) for value in re.findall(r"\[E(\d+)\]", sentence)}:
                    if reference < 1 or reference > len(rows):
                        audit.append({"claim": sentence, "evidence": f"E{reference}", "status": "needs_review", "reasons": ["Evidence identifier does not exist"]})
                        continue
                    chunk, document = rows[reference - 1]
                    work = type("Work", (), {"doi": document.doi, "is_retracted": bool(document.provenance.get("is_retracted"))})()
                    result = verifier.verify(sentence, chunk.text, work)
                    claim = SourceClaim(run_id=run.id, document_id=document.id, chunk_id=chunk.id, claim_text=sentence, numeric_assertions=[], verification_status=result.status, verification_details={"doi_resolves": result.doi_resolves, "numbers_grounded": result.numbers_grounded, "lexical_support": result.lexical_support, "reasons": result.reasons})
                    self.session.add(claim)
                    audit.append({"claim": sentence, "evidence": f"E{reference}", "status": result.status, "reasons": result.reasons})
        finally:
            crossref.close()
        verification = self._put_artifact(run, "claim_verification.json", json.dumps(audit, indent=2).encode(), "application/json")
        return WorkflowStage.REPORTING, {"artifact_id": str(artifact.id), "verification_artifact_id": str(verification.id), "claims_checked": len(audit)}

    def _report(self, run: ResearchRun):
        synthesis = self._latest_text(run, "evidence_synthesis.md")
        output = run_agent_stage("scientific_report", f"Hypothesis:\n{run.hypothesis}\n\nVerified synthesis:\n{synthesis}\n\nWrite abstract, methods/source limitations, findings, competing explanations, limitations, implications, future research, and references. Retain [E#] citations exactly.", "A complete scientific Markdown report.")
        artifact = self._put_artifact(run, "scientific_report.md", output.encode(), "text/markdown")
        return WorkflowStage.PDF_QA, {"artifact_id": str(artifact.id)}

    def _pdf(self, run: ResearchRun):
        report = self._latest_text(run, "scientific_report.md")
        sections = [("Scientific report", re.sub(r"[#*_`]", "", report))]
        documents = self.session.scalars(select(LiteratureDocument).where(LiteratureDocument.verified.is_(True)).limit(100)).all()
        citations = [Citation(str(i), doc.title, doc.doi, doc.source_url) for i, doc in enumerate(documents, 1)]
        temp_path = Path("tmp/pdfs") / str(run.id) / "scientific_report.pdf"
        result = render_scientific_pdf(temp_path, run.title, run.hypothesis, sections, citations)
        artifact = self._put_artifact(run, "scientific_report.pdf", temp_path.read_bytes(), "application/pdf")
        return WorkflowStage.ADAPTING, {"artifact_id": str(artifact.id), "pages": result["pages"]}

    def _substack(self, run: ResearchRun):
        report = self._latest_text(run, "scientific_report.md")
        output = run_agent_stage("substack", f"Adapt this approved scientific report into a Substack article. Preserve evidence IDs and uncertainty; introduce no new claims.\n\n{report}", "Accessible Substack-compatible Markdown with summary, evidence boundaries, and references.")
        artifact = self._put_artifact(run, "substack_article.md", output.encode(), "text/markdown")
        return WorkflowStage.VISUALS, {"artifact_id": str(artifact.id)}

    def _visuals(self, run: ResearchRun):
        article = self._latest_text(run, "substack_article.md")
        output = run_agent_stage("visuals", f"Create a visual plan for this article. Charts must list evidence IDs and exact source values. Image proposals must be labelled illustrative and include alt text.\n\n{article}", "A Markdown visual plan with provenance-ready chart specs and image proposals.")
        artifact = self._put_artifact(run, "visual_plan.md", output.encode(), "text/markdown")
        return WorkflowStage.CONTENT_REVIEW, {"artifact_id": str(artifact.id)}

    def _draft(self, run: ResearchRun):
        article = self._latest_text(run, "substack_article.md")
        package = build_publication_package(run.title, "", article, [])
        manifest = json.dumps({"title": package.title, "subtitle": package.subtitle, "markdown": package.markdown, "artifact_paths": package.artifact_paths, "snapshot_hash": package.snapshot_hash}, sort_keys=True).encode()
        artifact = self._put_artifact(run, "substack_publication.json", manifest, "application/json")
        return WorkflowStage.PUBLISH_REVIEW, {"artifact_id": str(artifact.id), "snapshot_hash": package.snapshot_hash}

    def _publish(self, run: ResearchRun):
        artifact = self._latest_artifact(run, "substack_publication.json")
        if not artifact:
            raise RuntimeError("Publication package is missing")
        approval = self.session.scalar(select(Approval).where(Approval.run_id == run.id, Approval.gate == WorkflowStage.PUBLISH_REVIEW.value, Approval.decision == "approved").order_by(Approval.created_at.desc()).limit(1))
        if not approval or approval.artifact_id != artifact.id or approval.snapshot_hash != artifact.sha256:
            raise RuntimeError("Final approval does not match the stored publication package")
        raw = self.storage.get(artifact.object_key).decode("utf-8")
        data = json.loads(raw)
        package = build_publication_package(data["title"], data["subtitle"], data["markdown"], data["artifact_paths"])
        ManualSubstackAdapter().publish(package, data["snapshot_hash"], self.settings.substack_publish_enabled)
        return WorkflowStage.PUBLISHED, {"snapshot_hash": package.snapshot_hash}
