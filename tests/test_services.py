import tempfile
import unittest
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from platform_app.models import Approval, Artifact, AuditEvent, Base, ResearchRun
from platform_app.repository import ResearchRunRepository, WorkflowConflict
from platform_app.services.clinical import validate_clinical_observation
from platform_app.services.literature import PubMedConnector, ScholarlyWork, merge_works
from platform_app.services.publishing import ManualSubstackAdapter, PublishingDisabled, build_publication_package
from platform_app.services.verification import ClaimVerifier
from platform_app.workflow import WorkflowStage


class FakeCrossref:
    def resolve_doi(self, doi):
        return object() if doi == "10.1234/verified" else None


class ServiceTests(unittest.TestCase):
    def test_pubmed_xml_parsing(self):
        xml = """<PubmedArticleSet><PubmedArticle><MedlineCitation><PMID>123</PMID><Article>
        <ArticleTitle>AuDHD sample</ArticleTitle><Abstract><AbstractText>N = 40 participants.</AbstractText></Abstract>
        <Journal><JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
        <AuthorList><Author><ForeName>Ada</ForeName><LastName>Test</LastName></Author></AuthorList>
        </Article></MedlineCitation><PubmedData><ArticleIdList><ArticleId IdType="doi">10.1234/verified</ArticleId></ArticleIdList></PubmedData>
        </PubmedArticle></PubmedArticleSet>"""
        work = PubMedConnector._parse(xml)[0]
        self.assertEqual(work.external_id, "123")
        self.assertEqual(work.doi, "10.1234/verified")
        self.assertEqual(work.publication_year, 2025)

    def test_merge_prefers_result_with_abstract(self):
        empty = ScholarlyWork("crossref", "1", "Same title", doi="10.1/a")
        rich = ScholarlyWork("pubmed", "2", "Same title", abstract="Evidence", doi="10.1/a")
        self.assertEqual(merge_works([empty], [rich])[0].abstract, "Evidence")

    def test_claim_verification_checks_numbers_and_quote(self):
        verifier = ClaimVerifier(FakeCrossref())
        work = ScholarlyWork("test", "1", "Test", doi="10.1234/verified")
        result = verifier.verify("The cohort included 40 participants.", "The cohort included 40 participants.", work)
        self.assertEqual(result.status, "verified")
        bad = verifier.verify("The cohort included 400 participants.", "The cohort included 40 participants.", work)
        self.assertEqual(bad.status, "needs_review")

    def test_clinical_ingestion_rejects_identifiers(self):
        result = validate_clinical_observation({"name": "Person", "notes": "email me at patient@example.com"})
        self.assertFalse(result.accepted)
        self.assertTrue(any("identifier" in reason.lower() or "email" in reason.lower() for reason in result.reasons))

    def test_substack_package_is_hash_locked_and_exportable(self):
        package = build_publication_package("Title", "Subtitle", "Body", ["figure.svg"])
        with tempfile.TemporaryDirectory() as directory:
            output = ManualSubstackAdapter().export_draft(package, Path(directory))
            self.assertTrue(output.exists())
        with self.assertRaises(PublishingDisabled):
            ManualSubstackAdapter().publish(package, "wrong", enabled=True)


class RepositoryTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine("sqlite+pysqlite:///:memory:")
        Base.metadata.create_all(self.engine, tables=[ResearchRun.__table__, Artifact.__table__, Approval.__table__, AuditEvent.__table__])
        self.session = Session(self.engine)
        self.repository = ResearchRunRepository(self.session)

    def tearDown(self):
        self.session.close()

    def test_gate_cannot_be_bypassed(self):
        run = self.repository.create("Test run", "A sufficiently detailed hypothesis for testing.", "tester")
        self.repository.advance(run.id, WorkflowStage.FORMALIZING, "worker")
        self.repository.advance(run.id, WorkflowStage.HYPOTHESIS_REVIEW, "worker")
        with self.assertRaises(WorkflowConflict):
            self.repository.advance(run.id, WorkflowStage.RETRIEVING, "worker")
        self.repository.approve(run.id, WorkflowStage.HYPOTHESIS_REVIEW, "reviewer", "snapshot")
        advanced = self.repository.advance(run.id, WorkflowStage.RETRIEVING, "worker")
        self.assertEqual(advanced.stage, WorkflowStage.RETRIEVING.value)


if __name__ == "__main__":
    unittest.main()
