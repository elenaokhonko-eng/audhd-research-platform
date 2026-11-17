> **Legacy document.** This describes the 2026 CrewAI prototype kept under the top-level `src/`, `config/` and `platform_app/` folders. It is not the platform's architecture. The current design is in [`docs/architecture/`](architecture/README.md).

# AuDHD research and publishing platform architecture

## Product boundary

The platform turns an approved hypothesis into a source-grounded scientific report, a visually verified PDF, and a separately reviewed Substack draft. It is a research-support and publishing system, not a clinical decision system. Outputs must not diagnose patients or replace professional judgment.

## Durable workflow

1. Submit hypothesis.
2. Formalize hypothesis.
3. Human approval or edit.
4. Retrieve scientific papers and permitted datasets.
5. Extract claims and verify citations, quotations, and statistics against stored source passages.
6. Produce a scientific report.
7. Render the report as PDF and perform automated plus human visual QA.
8. Adapt the approved report into a separate Substack article.
9. Generate charts, figures, and image proposals with provenance.
10. Human content and visual approval.
11. Create a Substack draft when an authorized integration is configured.
12. Obtain final approval for the immutable draft snapshot.
13. Publish only when publishing is enabled and the approved snapshot hash matches.

Every transition is persisted in PostgreSQL. Long-running work is executed by a background worker; approval stages have no automatic timeout transition.

## Governed knowledge architecture

### Literature zone

Stores bibliographic metadata, licensed/full-text source objects, page-aware chunks, extracted claims, DOI verification results, and embeddings. Retrieval is hybrid: metadata/keyword filtering plus pgvector similarity. Every generated claim must carry source document, passage, page, extraction version, and verification state.

### Clinical zone

Stores pseudonymous subjects and structured longitudinal observations. Direct identifiers and the re-identification mapping must remain in the psychiatrist's controlled source system or a separate encrypted identity vault. Raw case files are not inserted into the general literature index.

Clinical ingestion requires documented legal basis/consent, data-use purpose, retention policy, field-level classification, de-identification review, and an auditable export/delete procedure. Free text must pass deterministic identifier detection and human review before embedding.

### Semantic bridge

A shared concept table maps literature entities and clinical observations onto governed concepts and external terminologies where appropriate. Analyses connect zones through these concepts and authorized cohort aggregates. Access policies decide whether a user receives public literature, de-identified passages, aggregate clinical statistics, or no clinical result.

This structure supports later ML by keeping observations in analysis-ready tables with stable definitions, units, missingness codes, provenance, cohort version, and label-generation history. Embeddings support discovery; they do not replace the structured feature store used for statistical or machine-learning analysis.

## Services

- Streamlit dashboard: submission, status, knowledge exploration, artifact preview, and approvals.
- FastAPI service: authenticated application boundary and workflow commands.
- Celery worker: long-running retrieval, agent, verification, rendering, and publishing jobs.
- PostgreSQL + pgvector: workflow state, provenance, structured data, concepts, and embeddings.
- S3-compatible object storage: source documents, extracted text, reports, PDFs, charts, and images.
- Redis: task queue; production deployments should enable persistence or use a managed equivalent.
- LangSmith: CrewAI/OpenAI traces, tagged with research-run and workflow-stage identifiers.
- Secret manager: model, literature-source, storage, database, and publishing credentials.

## Deployment

Keep service boundaries portable. A first production target can use Azure Container Apps, PostgreSQL Flexible Server with pgvector support, Azure Blob Storage, Azure Cache for Redis, and Key Vault. Equivalent Google Cloud or AWS managed services can be substituted without changing domain models.

Clinical data must not enter a cloud environment until the hosting region, data-processing agreements, access controls, encryption, backups, incident response, and applicable ethics/privacy approvals have been reviewed by qualified institutional, legal, and information-security stakeholders.

## Substack boundary

The publisher is an adapter, disabled by default. It may create or publish only through an authorized Substack capability. If no supported publishing operation is available, the system exports an approved HTML/Markdown package for manual insertion. Browser automation is not a production publishing contract.
