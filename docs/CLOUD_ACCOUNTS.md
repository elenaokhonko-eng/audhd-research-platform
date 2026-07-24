# Cloud and external account setup

Create accounts only for the environment you are ready to operate. Do not upload clinical records during initial development or public demonstrations.

## Required for local end-to-end testing

| Service | Where to register | Purpose | Variables |
|---|---|---|---|
| LLM provider | Existing Kimi Code account or another OpenAI-compatible provider | CrewAI generation | `OPENAI_API_KEY`, `OPENAI_API_BASE`, `OPENAI_MODEL_NAME` |
| LangSmith | <https://smith.langchain.com> | Traces and debugging | `LANGSMITH_API_KEY`, `LANGSMITH_PROJECT`, `LANGSMITH_ENDPOINT` |
| Embedding provider | <https://platform.openai.com> or a compatible embedding service | pgvector embeddings | `EMBEDDING_API_KEY`, `EMBEDDING_BASE_URL`, `EMBEDDING_MODEL` |
| Docker Desktop | <https://www.docker.com/products/docker-desktop/> | Local PostgreSQL, Redis, MinIO, API, worker, dashboard | None |

Kimi's coding endpoint may not expose an embedding model. Keep generation and embedding credentials separate.

## Scientific-source accounts

| Service | Setup | Notes |
|---|---|---|
| PubMed/NCBI | Create an NCBI account at <https://www.ncbi.nlm.nih.gov/account/> and generate an API key | Optional at low request volume; configure `NCBI_API_KEY`. Always set `RESEARCH_CONTACT_EMAIL`. |
| OpenAlex | Create an API account/key through <https://openalex.org> / <https://developers.openalex.org> | Configure `OPENALEX_API_KEY`. Plans and limits can change; select the lowest tier suitable for testing. |
| Crossref | No normal API account is required | Set `RESEARCH_CONTACT_EMAIL` so requests identify the application responsibly. |
| Full-text publishers | Institution/library and publisher-specific access | Access rights differ by paper. Store license and provenance metadata; never bypass a paywall. |

## Recommended first production cloud: Azure

Use one cloud initially. Azure is a coherent option for this architecture because Container Apps, Entra ID, Key Vault, managed PostgreSQL, Blob Storage, and managed Redis can be governed together. Confirm region and clinical-data eligibility before uploading any clinical information.

Create:

1. An Azure subscription and a dedicated production tenant/subscription boundary.
2. Azure Container Registry for images.
3. Azure Container Apps environment for API, dashboard, and worker.
4. Azure Database for PostgreSQL Flexible Server with pgvector available.
5. Azure Blob Storage with private containers and lifecycle rules.
6. Azure Managed Redis or an approved equivalent.
7. Azure Key Vault using managed identities rather than stored cloud keys.
8. Microsoft Entra ID application registrations for dashboard OIDC and API authentication.
9. Log Analytics/Application Insights with clinical payload logging disabled.

Before clinical use, engage qualified privacy/security/legal and research-ethics stakeholders to approve data residency, consent/legal basis, data-processing agreements, retention, backup, breach response, access reviews, and cross-border processing.

## Authentication

For Microsoft Entra ID:

1. Register a web application.
2. Add the dashboard redirect URI: `https://YOUR_DASHBOARD/oauth2callback`.
3. Create a client secret in Key Vault or use an approved secretless mechanism.
4. Copy `.streamlit/secrets.toml.example` only for local testing; production secrets must be injected at runtime.
5. Set `OIDC_REQUIRED=true`, `TRUSTED_AUTH_PROXY=true`, and `ADMIN_EMAILS` in production.

## Substack

Create or use your existing publication at <https://substack.com>. No confirmed broad official write API is assumed by this repository. The implemented adapter creates a hash-locked Markdown package for manual import into the Substack editor. Keep `SUBSTACK_PUBLISH_ENABLED=false` unless Substack grants you a documented, authorized publishing integration and the adapter is implemented against that contract.

## GitHub repository settings

For the public repository:

1. Enable private vulnerability reporting under **Settings → Security**.
2. Enable Dependabot alerts and secret scanning/push protection if available.
3. Protect `main` and require pull requests plus passing checks.
4. Add production secrets only through GitHub Environments/Actions secrets; never repository files.
5. Choose a software license explicitly before accepting external reuse or contributions.

## Clinical data onboarding prerequisites

Do not create a cloud clinical-data account or upload the psychiatrist's database until all of the following exist:

- documented authority/consent and approved research purposes;
- a data dictionary and export specification;
- separation of direct identifiers from research pseudonyms;
- a tested de-identification and free-text review procedure;
- data-use agreements and an approved secure transfer mechanism;
- role-based access, audit logging, retention, deletion, and subject-rights procedures;
- a synthetic-data rehearsal of the entire ingestion and ML export process.
