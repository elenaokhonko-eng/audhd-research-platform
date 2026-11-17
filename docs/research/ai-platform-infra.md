# AI platform infrastructure: self-host versus buy, on Google Cloud (asia-southeast1)

Research date: 2026-11-16. Prices are USD list prices from the page and date named beside them.
Marks: [unverified] = stated from model knowledge or a secondary source, page not opened in this session. [inference] = my own reasoning or arithmetic from opened pages.

Method limit to read first. The shared web-search budget for this turn ran out after item 6. Items 7 and 8 could not be searched, and direct fetches of Google's Resource Manager, IAM, Cloud Run identity and credit-programme pages were refused by the fetch permission system. Those two sections are therefore written from model knowledge and marked [unverified]. The blocked URLs are listed at the end so they can be opened by hand.

## Decision table

| Topic | Cheapest adequate option | Monthly cost (USD) | Caveat |
|---|---|---|---|
| 1. LLM gateway | LiteLLM open-source proxy on Cloud Run, config file only at first, image pinned by digest | About 0 to 25 for Cloud Run [inference]; add about 13 if virtual keys and spend tables are wanted | Two supply-chain compromises in 2026 (March on PyPI, October on PyPI and Docker tags). Logging to a GCS bucket or Pub/Sub is an Enterprise feature |
| 2. Small shared Postgres | Cloud SQL Enterprise edition, db-f1-micro, 10 GB SSD, asia-southeast1 | About 13 to 14 | 0.6 GB RAM, shared core, no SLA. Enough for LiteLLM tables and pgvector at 5,000 chunks, tight if Postiz or Phoenix share it |
| 3. LLM observability | Genkit Monitoring (Firebase telemetry plugin) and OpenTelemetry into Cloud Trace and Cloud Logging | 0 inside the free allotments | No prompt-management or evaluation UI. Langfuse self-hosting needs four data stores and is not a Cloud Run fit |
| 4. Instagram and Threads posting | Call Meta's official APIs directly from a small Cloud Run job, own Meta app, Standard Access, own accounts only | 0 beyond existing Cloud Run | 60-day tokens must be refreshed. Instagram images must be JPEG at a public URL. Postiz self-hosted needs Postgres, Redis and Temporal on an always-on VM |
| 5. Her own voice model | Prompt plus retrieval on Gemini Flash now; Gemini Flash supervised tuning as the next step | About 2 to 7; tuning adds a one-off 5 to 30 | LoRA on Cloud Run GPU costs about 3 to 90 a month depending on how requests are batched, plus her time |
| 6. Vector search, 5,000 chunks | Firestore `findNearest` on the existing database | 0 | Flat index only, 2,048 dimensions maximum, 1,000 results maximum |
| 7. Organisation | One organisation, a folder per venture, separate projects; confirm the billing arrangement before linking unrelated projects | 0 | Organisations cannot nest. Programme terms were not retrievable in this session |
| 8. Agent credentials | One service account per Cloud Run service, per-secret IAM bindings in Secret Manager, Workload Identity Federation for CI | About 0 to 1 | Third-party tokens (Stripe, Meta, Substack cookie) need her own rotation jobs. A Substack cookie cannot be scoped |

## 1. LiteLLM proxy on Cloud Run

Licence. The docs describe the AI Gateway and Python SDK as open source, with Enterprise as "a license-key add-on on the same Gateway image" (https://docs.litellm.ai/docs/enterprise.md). The repository licence is MIT with the `enterprise/` folder under a separate commercial licence [unverified, LICENSE file not opened].

Works without a database (https://docs.litellm.ai/docs/proxy/docker_quick_start.md).
- The quick start says: "For API access without database-backed model management, virtual keys, or spend tracking, run the same image with a config file."
- That covers `model_list` in `config.yaml`, load balancing, routing, fallbacks and authentication with the single master key.
- Without a database `litellm_settings.max_budget` is not enforced, and a request that carries a virtual key fails with "No connected db."
- The auto router is a beta feature in v1.94.0 and later (https://docs.litellm.ai/docs/proxy/auto_routing.md). The complexity router is configured as `model: auto_router/complexity_router` with a `tiers` map. Its default heuristic scorer makes "Zero API calls, sub-millisecond" and needs no database, embedding model or external service. The LLM classifier and semantic keyword matching are optional. Only the savings report needs "a configured proxy database and enabled spend logging". The older semantic auto router is deprecated.

Requires Postgres (https://docs.litellm.ai/docs/proxy/virtual_keys and https://docs.litellm.ai/docs/proxy/db_info.md).
- Virtual keys: "Need a postgres database (e.g. Supabase, Neon, etc)", set through `DATABASE_URL`, plus a master key that starts with `sk-`.
- The database holds "Virtual Keys, Organizations, Teams, Users, Budgets, and more" plus per-request spend logs, daily spend roll-ups and audit logs. PostgreSQL is the only database named.
- So virtual keys, per-key or per-team budgets, spend tracking, models stored from the UI and the useful parts of the Admin UI all need Postgres. `LITELLM_SALT_KEY` encrypts provider keys stored through the UI and cannot be rotated in place.
- BigQuery and Firestore cannot substitute. The docs name only PostgreSQL. [inference: the proxy uses a Prisma schema for Postgres.]

Logging callbacks that need no paid service (https://docs.litellm.ai/docs/proxy/logging).
- Not marked Enterprise: OpenTelemetry (`callbacks: ["otel"]`), Langfuse, a custom callback class (`callbacks: custom_callbacks.proxy_handler_instance`), s3, Langsmith, Arize, MLflow, DynamoDB, AWS SQS.
- Marked Enterprise on that page: GCS bucket (`gcs_bucket`), GCS Pub/Sub (`gcs_pubsub`), Azure Blob Storage and "Custom Callback APIs".
- BigQuery is not a direct destination. It appears only as a consumer of the Pub/Sub output.
- Free routes into her own project: the `otel` callback exporting to Cloud Trace; or a custom Python callback class that publishes to her existing Pub/Sub topic or writes to BigQuery with Google's client library; or plain JSON to stdout, which Cloud Run sends to Cloud Logging, with a log sink to BigQuery [inference for all three, not tested].

Vertex AI and Gemini (https://docs.litellm.ai/docs/providers/vertex.md).
- Config uses `model: vertex_ai/<model>` with `vertex_project` and `vertex_location`. `vertex_credentials` is optional.
- Authentication options are a service-account JSON, Application Default Credentials, or a Workload Identity Federation config file.
- On Cloud Run the page says that once the service account has the Vertex AI User role, "LiteLLM will have automatic access to all Vertex AI endpoints." No key file is needed.
- The `gemini/` prefix targets the Gemini API with `GEMINI_API_KEY` instead.

Genkit TypeScript client (https://genkit.dev/docs/integrations/openai-compatible/).
- The plugin is `@genkit-ai/compat-oai` (1.31.0 was the version on jsDelivr on 2026-11-16).
- Use `openAICompatible({ name: 'litellm', apiKey: <key>, baseURL: 'https://<proxy>/v1' })`, then reference models as `litellm/<model_name>`.
- `apiKey` is required even when the server ignores it. Config options such as temperature pass through.

Supply-chain incidents in 2026.
- 24 March 2026 (LiteLLM's own post, https://docs.litellm.ai/blog/security-update-march-2026). PyPI versions 1.82.7 and 1.82.8 carried a credential stealer that harvested environment variables, SSH keys, cloud credentials, Kubernetes tokens and database passwords and posted them to `models.litellm.cloud`. They were live from 10:39 UTC "for about 40 minutes before being quarantined by PyPI". The post says "Customers running the official LiteLLM Proxy Docker image were not impacted." The suspected origin was the Trivy dependency in the CI/CD scanning workflow. Clean release v1.83.0 followed, with cosign image signatures from v1.83.0-nightly.
- 21 October 2026 (third-party advisory that cites LiteLLM's incident report and root-cause analysis, https://www.konfirmity.com/advisories/litellm-1-107-0-supply-chain-compromise; LiteLLM's own report was not opened). A malicious 1.107.0 was published through LiteLLM's own release pipeline with stolen credentials. It affected PyPI (about 11:39 to 13:23 UTC) and this time also Docker images tagged `v1.107.0`, `latest`, `main-latest` and `main-stable` on GHCR and Docker Hub. The payload ran at Python start-up and exfiltrated credentials to `www.litellm.dev`. The stated root cause was a service master key committed to a public repository in May and never revoked. Clean versions named are 1.108.0 and 1.106.7. The cosign signing key was replaced on 24 October.
- The same advisory lists a separate Enterprise file-read flaw, GHSA-w4c7-34wj-hqm8, fixed in 1.103.10, 1.104.8, 1.105.6 and 1.106.5.

Pinning practice that follows from both incidents.
- Never deploy `latest`, `main-latest` or `main-stable`. Pin the image by `sha256` digest and copy it into her own Artifact Registry.
- Verify the cosign signature with the post-24-October key before promoting a digest.
- Wait several days after a release before adopting it. Both malicious releases were removed within hours.
- Give the proxy its own service account with only Vertex AI User and access to its own secrets, so a compromised proxy cannot read Firestore, BigQuery or other agents' secrets.
- Rotate the master key, provider keys and database password if an affected version ever ran.

Enterprise-only features to avoid depending on (https://docs.litellm.ai/docs/proxy/enterprise and https://docs.litellm.ai/docs/enterprise.md): SSO and SCIM for the Admin UI, audit logs with retention, JWT auth, IP allow lists, team-based logging, the built-in secret-manager integrations (including Google Secret Manager), tag-based budgets, GCS bucket and Pub/Sub logging, custom Swagger branding. Enterprise pricing is by quote. The secret-manager gap does not matter on Cloud Run, because Cloud Run can mount Secret Manager secrets as environment variables itself.

Cost and design note [inference]. The proxy scales to zero on Cloud Run, but each LLM call holds a request open. At 100,000 calls of about 10 seconds on 1 vCPU that is about 1,000,000 vCPU-seconds against a free 180,000, so roughly 20 a month at request-based rates. At 10,000 calls it is free. If she only needs Gemini through Genkit, Genkit's native Vertex AI plugin avoids the extra hop, the cold start and the supply-chain exposure. The proxy earns its place when she needs several providers, fallbacks, or per-agent keys and budgets.

## 2. Cheapest Postgres on Google Cloud

Cloud SQL list prices (https://cloud.google.com/sql/pricing, opened 2026-11-16; the fetched text did not label the region and is presumed to be Iowa).
- db-f1-micro 0.0105 per hour, db-g1-small 0.035 per hour. The page notes shared-core types are not covered by the Cloud SQL SLA. Shared-core exists only in Enterprise edition.
- Dedicated core, Enterprise edition: 0.0413 per vCPU-hour and 0.007 per GiB-hour. The smallest 1 vCPU and 3.75 GB instance is about 49 a month in Iowa [inference].
- SSD storage about 0.17 per GiB-month, backups about 0.08 per GiB-month, idle IPv4 address 0.01 per hour.
- Singapore: db-f1-micro compute is 11 a month and Iowa is 8 a month (https://www.bytebase.com/dbcost/cloudsql/instance/db-f1-micro/, page dated "Updated November 9, 2026").

| Option in asia-southeast1 | Estimate per month | Basis |
|---|---|---|
| db-f1-micro (shared core, 0.6 GB RAM), 10 GB SSD, 7 backups | About 13 to 14 | 11 compute, about 2 storage, under 1 backups [inference for storage, Singapore storage rate not captured] |
| db-g1-small (shared core, 1.7 GB RAM), 10 GB SSD | About 38 | Iowa 25.55 scaled by the same Singapore ratio [inference] |
| Dedicated 1 vCPU, 3.75 GB, 10 GB SSD | About 70 | Iowa 49 scaled [inference] |
| AlloyDB, 1 vCPU, 8 GB (C4A) | About 115 to 140 plus storage | See below |
| Postgres in a container on an e2-micro VM | About 8 to 10 [unverified] | Not free in Singapore |

Stop and start on a schedule.
- Cloud SQL stops when the activation policy is set to `NEVER`. The docs say "charges for storage and IP addresses continue to apply" (https://docs.cloud.google.com/sql/docs/postgres/start-stop-restart-instance).
- Google documents the scheduled pattern: Cloud Scheduler publishes to Pub/Sub, and a Cloud Run function sets the policy to `ALWAYS` or `NEVER` (https://docs.cloud.google.com/scheduler/docs/start-and-stop-sql-server-instances-on-a-schedule). The tutorial is written for SQL Server. The activation policy it sets is the same for Postgres [inference].
- It is not worth doing for db-f1-micro. Stopping 12 hours a day saves about 5.50 of compute, and an idle public IPv4 then costs 0.01 an hour [inference]. LiteLLM also needs the database whenever a keyed request arrives.

AlloyDB (https://cloud.google.com/alloydb/pricing and https://cloud.google.com/blog/products/databases/c4a-axion-processors-for-alloydb-now-ga/).
- The smallest shape is "1 vCPU shape with 8GB of memory with C4A", intended for "development and sandbox environments", and it "does not come with uptime SLAs".
- N2 and C4A cost 0.06608 per vCPU-hour and 0.0112 per GiB-hour in the default listed region. One vCPU and 8 GB is 0.1557 an hour, about 114 a month, plus storage at about 0.30 per GiB-month [inference; Singapore is higher].
- The free trial is 30 days with an 8 vCPU instance, one per project (https://docs.cloud.google.com/alloydb/docs/free-trial-cluster).
- AlloyDB Omni is a downloadable container with a free developer edition; production use needs a paid subscription [unverified]. It gives no saving over plain Postgres for this workload.

Plain Postgres on a small VM.
- The Always Free e2-micro applies only in us-west1, us-central1 and us-east1, with 30 GB of standard persistent disk (third-party summary, https://agentdeals.dev/gcp-free-tier-2026; Google's own free-tier page was not reachable). It is not free in Singapore.
- An e2-micro has 1 GB of RAM. In Singapore it saves only a few dollars against db-f1-micro and moves backups, patching and recovery to her.

Can BigQuery or Firestore substitute. Not for LiteLLM (Postgres only, see item 1). Not for Postiz either, which needs PostgreSQL 14 or later through Prisma (item 4). For the search index, yes: Firestore vector search removes the need for pgvector (item 6).

Recommendation. If nothing else needs Postgres, do not create one: run LiteLLM from a config file and keep search in Firestore. If virtual keys and budgets are wanted, one db-f1-micro at about 13 to 14 a month is the cheapest managed choice.

## 3. LLM observability without a paid SaaS

Langfuse self-hosted (https://langfuse.com/self-hosting.md; the page is now labelled v4 and keeps the v3 architecture).
- Required: Langfuse Web, Langfuse Worker, PostgreSQL, ClickHouse, Redis or Valkey, and S3-compatible blob storage. All four data stores are confirmed.
- The GCP route is the official Terraform module `langfuse/langfuse-terraform-gcp` or the Kubernetes Helm chart (https://langfuse.com/self-hosting/deployment/gcp). Cloud Run is not mentioned on either page. Docker Compose is described as a "Single VM without high availability, scaling, or backups."
- Realistic on Cloud Run: no [inference]. Web and Worker are stateless containers, but ClickHouse needs a persistent disk and Redis needs an always-on instance, so the practical minimum is one VM running Compose at roughly 100 a month or more [unverified estimate], or a GKE cluster.
- Ownership: Langfuse joined ClickHouse in January 2026, and code outside `ee/` stays MIT with "No licensing changes planned" (secondary source, https://www.developersdigest.tech/blog/llm-observability-acquisitions-2026).

Langfuse Cloud free tier (https://langfuse.com/pricing.md, opened 2026-11-16).
- Hobby: 50k units a month, 30 days data access, 2 users, no overage option.
- Core: 29 a month with 100k units, then 8 per 100k units, 90 days data access.
- A unit is "any tracing data point sent to the platform" (a trace, each span, event or generation, and each score). One LLM call is at least two units, so 100,000 calls a month is at least 200,000 units. Hobby covers about 25,000 simple calls [inference].

Google-native options.
- Genkit Monitoring (https://genkit.dev/docs/observability/getting-started/). Call `enableFirebaseTelemetry()` from `@genkit-ai/firebase`, or set `ENABLE_FIREBASE_MONITORING=true`. It needs the Cloud Logging, Cloud Trace and Cloud Monitoring APIs and the roles Monitoring Metric Writer, Cloud Trace Agent and Logs Writer on the service account. The project must be on the Blaze plan. The page lists no charge of its own: the telemetry is billed at Google Cloud Observability rates.
- Google Cloud Observability pricing (https://cloud.google.com/products/observability/pricing, opened 2026-11-16). Cloud Logging: first 50 GiB per project per month free, then 0.50 per GiB, with 30 days of retention included. Cloud Trace: first 2.5 million spans per billing account per month free, then 0.20 per million. Cloud Monitoring: first 150 MiB of chargeable metrics per billing account free.
- Estimate for 100,000 LLM calls a month [inference]: 5 to 10 spans a call is 0.5 to 1 million spans, and 5 KB of logged input and output a call is about 0.5 GB. Both sit inside the free allotments, so the cost is 0.
- Genkit's Developer UI already shows traces locally at no cost.

Lighter self-hosted tools.
- Arize Phoenix: one containerised application with web UI, trace collector and SQL backend. SQLite is the default and PostgreSQL 14 or later is the production store (https://www.arize.com/docs/phoenix/self-hosting/architecture.md). Licence is Elastic License 2.0; self-hosting "is free and fully permitted" and "There are no feature gates" (https://www.arize.com/docs/phoenix/self-hosting/license.md). It can run as one Cloud Run service against the shared Postgres [inference]. ELv2 forbids offering it to others as a managed service, which does not affect internal use.
- MLflow 3: one `mlflow server` process, SQLite by default since 3.7.0, PostgreSQL to scale, GCS for artifacts, LLM tracing supported (https://mlflow.org/docs/latest/self-hosting/). Apache-2.0 [unverified]. An OpenTelemetry ingestion section exists in its docs [unverified, URL seen in search, not opened].
- Opik: Java backend, Python backend, frontend, ClickHouse, Zookeeper, MySQL, Redis and MinIO (https://www.comet.com/docs/opik/self-host/architecture.md). Too heavy for one person.
- Helicone: joined Mintlify on 3 March 2026 and is "in maintenance mode"; Apache-2.0 (secondary source above). Avoid for new work.

Recommendation for under 100,000 calls a month. Use Genkit Monitoring for the TypeScript agents and the OpenTelemetry SDK exporting to Cloud Trace for the Python services, with prompts and outputs in Cloud Logging and an optional log sink to BigQuery for cost analysis. That is 0 a month and adds no vendor. Add Phoenix on Cloud Run with the shared Postgres only when she wants an evaluation and prompt-comparison UI.

## 4. Postiz versus calling Meta's APIs directly

Postiz.
- Licence: the README says the source is "available under the AGPL-3.0 license" (https://cdn.jsdelivr.net/gh/gitroomhq/postiz-app@main/README.md).
- What AGPL-3.0 asks if she modifies it and only she uses it [inference from the standard reading of section 13; licence text not opened; not legal advice]. She may modify and run it privately. The duty to offer source code is owed to users who interact with the modified program over a network. If she is the only user, nobody else is owed the source and she need not publish. If team members, clients or the public use her modified instance, she must offer them the modified source under AGPL-3.0. Her own separate services that only call Postiz over its HTTP API are not covered by the licence.
- Architecture (https://docs.postiz.com/installation/system-requirements.md): PostgreSQL 14+, Redis 6+, and Temporal, which is "required since v2.12.0". Storage is local disk or Cloudflare R2. The stack is Next.js, NestJS and Prisma.
- Resources: 2 vCPU and 2 GB RAM minimum, 4 vCPU and 8 GB recommended, 20 GB disk. The Compose setup "has been tested with" Ubuntu 24.04, 2 GB RAM, 2 vCPUs (https://docs.postiz.com/installation/docker-compose.md). The canonical Compose file lives in `gitroomhq/postiz-docker-compose` and includes a Temporal UI on port 8080.
- Cloud Run: not mentioned in the docs. It is a poor fit [inference]: Temporal and Redis are always-on stateful services and Postiz runs several long-lived processes. The realistic host is one VM of 4 to 8 GB at roughly 25 to 60 a month [unverified estimate], which is the same price band as the tools she wants to avoid.
- Providers: Instagram and Threads are both in the README's list of 14 channels.
- API and MCP: "Public API & webhooks" are included in the self-hosted edition, and for MCP and the CLI "you point the MCP / CLI at your own instance". The hosted MCP endpoint is `https://mcp.postiz.com/mcp` (https://postiz.com/llms.txt). The public API reference pages were blocked, so the rate limit is not confirmed.
- A self-hosted Postiz still uses her own Meta app credentials, so it does not remove the Meta app set-up below [unverified].

Instagram direct (https://developers.facebook.com/docs/instagram-platform/content-publishing/ and https://developers.facebook.com/documentation/instagram-platform/overview).
- Account: an Instagram professional account (business or creator). With Instagram Login no Facebook Page is needed: "Instagram Login can serve Instagram-only app users."
- Instagram API with Instagram Login uses host `graph.instagram.com` and permissions `instagram_business_basic` and `instagram_business_content_publish`. The Facebook Login variant uses `instagram_basic`, `instagram_content_publish` and `pages_read_engagement`.
- Flow: `POST /<IG_ID>/media` creates a container, `POST /<IG_ID>/media_publish` publishes it, and `GET /<CONTAINER_ID>?fields=status_code` polls video processing.
- Media: images are JPEG only. Reels, stories and carousels of up to 10 items are supported. `alt_text` works for image posts. Media must be on a publicly accessible server at publish time. Shopping tags, branded content tags and filters are not supported. Resumable upload is only for Facebook Login.
- Rate limit: the publishing guide says 100 API-published posts in a moving 24 hours, with a carousel counting as one. The `content_publishing_limit` reference says the quota is "currently 50" (https://developers.facebook.com/docs/instagram-platform/instagram-graph-api/reference/ig-user/content_publishing_limit). Meta's pages disagree, so plan for 50. General calls are limited to 4800 times impressions per 24 hours.
- Tokens: short-lived for one hour, then a long-lived token that "is valid for 60 days and can be refreshed".

Threads direct (https://developers.facebook.com/documentation/threads/overview.md and https://developers.facebook.com/documentation/threads/get-started).
- Permissions: `threads_basic` (all endpoints), `threads_content_publish`, `threads_manage_replies` (POST on reply endpoints), `threads_read_replies` (GET on reply endpoints), `threads_manage_insights` (GET on insights endpoints).
- Limits per moving 24 hours: 250 posts ("Threads profiles are limited to 250 API-published posts"), 1,000 replies, 100 deletions.
- Content: text up to 500 characters; images JPEG or PNG up to 8 MB; video MOV or MP4 up to 300 seconds and 1 GB; carousels of 2 to 20 items.
- Tokens: short-lived for 1 hour; long-lived for 60 days, refreshed through `GET /refresh_access_token`.

App review when the only user is the app owner.
- Instagram: the app review page lists App Review as "Not required" for an app that is "only for a business I own or manage" on Standard Access (https://developers.facebook.com/documentation/instagram-platform/app-review). Advanced Access, App Review and Business Verification apply only when serving accounts she does not own.
- Threads: add her own profile as a "Threads Tester" under App roles and accept the invitation. Testers with a role can grant permissions without app review. Review is required only when "app users without a role" must grant permissions.
- Development mode caveat (https://developers.facebook.com/documentation/development/build-and-test/app-modes): "Any data generated while an app is in Development mode, such as test posts, can only be seen by role users." In Live mode, Standard Access permissions still work for role users. So the safe set-up is own accounts as role users, Standard Access, no App Review, and one test post checked from a logged-out browser before relying on it [inference from the two pages].

Verdict. Two channels through the official APIs is one scheduled Cloud Run job, a Firestore queue and one token-refresh job. It needs no new database and no always-on host. Postiz is worth it only if she wants its calendar UI or many more channels.

## 5. Hosting her own small fine-tuned model

Cloud Run with GPU (https://docs.cloud.google.com/run/docs/configuring/services/gpu, opened 2026-11-16).
- GPU types: NVIDIA L4 (24 GB VRAM) and NVIDIA RTX PRO 6000 Blackwell (96 GB VRAM), one GPU per instance.
- Both are available in asia-southeast1. L4 regions: asia-southeast1, europe-west1, europe-west4, us-central1, plus asia-south1 and us-east4 by invitation.
- Minimums: L4 needs 4 CPU and 16 GiB (8 CPU and 32 GiB recommended). RTX PRO 6000 needs 20 CPU and 80 GiB.
- Instance-based billing is required. Services "can scale down to zero". Instances with pre-installed drivers "start in approximately 5 seconds"; model loading comes on top.
- New projects get 3 L4 GPUs of quota automatically with zonal redundancy off.
- Cloud Run jobs also take a GPU in asia-southeast1, always without zonal redundancy (https://docs.cloud.google.com/run/docs/configuring/jobs/gpu).

Cloud Run GPU price (https://cloud.google.com/run/pricing, opened 2026-11-16).
- L4: 0.0001867 per second without zonal redundancy (0.67 an hour), 0.0002909 with it (1.05 an hour).
- RTX PRO 6000: 0.00036522 per second without zonal redundancy (1.31 an hour).
- Instance-based CPU 0.000018 per vCPU-second and memory 0.000002 per GiB-second, as listed. Singapore is a Tier 2 region and the page showed no separate Tier 2 figures.
- An L4 instance with 4 vCPU and 16 GiB is therefore about 0.00029 a second, about 1.05 an hour [inference].
- Billing covers "the entire lifetime" of an instance "from the time the container is started to when it is terminated, with a minimum of 1 minute". The idle minutes before scale-down are billed.

Serving a LoRA.
- Google's tutorial serves Gemma with Ollama (https://docs.cloud.google.com/run/docs/tutorials/gpu-gemma-with-ollama). It now uses Gemma 4 E2B and E4B and sets `OLLAMA_NUM_PARALLEL` equal to `--concurrency`.
- Best practices (https://docs.cloud.google.com/run/docs/configuring/services/gpu-best-practices): download models from Cloud Storage at start-up or bake them into the image ("best suited for smaller models less than 10 GB"); "Choose 4-bit quantized models"; prefer fast-loading formats such as GGUF; make the start-up probe pass only once the model is loaded.
- Two workable shapes [inference]: merge the adapter and export to GGUF for Ollama, or keep the adapter separate and serve it with vLLM, which exposes an OpenAI-compatible endpoint that LiteLLM or the Genkit plugin can call. A 4-bit 4B model is about 3 GB and a 12B about 8 GB, both inside an L4.

Vertex AI endpoints for open or custom models (https://cloud.google.com/vertex-ai/pricing, opened 2026-11-16).
- "You pay for each model deployed to an endpoint, even if no prediction is made. You must undeploy your model to stop incurring further charges."
- Only legacy MLS1 machine types scale to zero; other deployments "cannot scale down to zero nodes".
- Prediction node-hours: g2-standard-4 with one L4 is 0.81293, g2-standard-8 is 0.98181. The Model Garden Gemma tutorial defaults to g2-standard-12 with one L4 (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/model-garden/deploy-and-inference-tutorial).
- An always-on g2-standard-4 endpoint is about 593 a month [inference]. This is the most expensive path for 300 generations.

Vertex AI supervised tuning of Gemini (https://cloud.google.com/vertex-ai/generative-ai/pricing, opened 2026-11-16).
- Training price per 1,000 training tokens: Gemini 2.5 Flash-Lite 0.0015, Gemini 2.5 Flash 0.005, Gemini 3.1 Flash-Lite and 3.5 Flash-Lite 0.003, Gemini 3.5 Flash 0.01, Gemini 2.5 Pro 0.025. That is 1.50, 5, 3, 10 and 25 per million.
- Training tokens are "the total number of tokens in your training dataset, multiplied by your number of epochs."
- Serving: "For model inference starting from Gemini 3, tuned model endpoint prediction price will be 1.5 times of the base model in non-global region. Tuned model endpoint has the same prediction price as the base model in global region. Old Gemini models prediction price stays the same as the base model."
- No minimum or hosting fee is listed for tuned Gemini models.
- Base prices per million tokens: Gemini 2.5 Flash 0.30 input and 2.50 output; 2.5 Flash-Lite 0.10 and 0.40; Gemini 3.8 Flash global 0.75 and 3.75 until 31 December 2026, then 1.50 and 7.50.
- Data guidance (https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini-supervised-tuning-about): "we recommend that you start with 100 examples", scale "up to thousands of examples if needed", and "The quality of the dataset is far more important than the quantity." The format is JSONL in a Cloud Storage bucket.

Fine-tuning with Unsloth.
- Licence: Apache-2.0 for the `unslothai/unsloth` repository (repository metadata via https://awesome.ecosyste.ms/projects/github.com%2Funslothai%2Funsloth). The licence of the separate Unsloth Studio UI was not confirmed.
- Hardware (https://unsloth.ai/docs/get-started/fine-tuning-for-beginners/unsloth-requirements.md): NVIDIA GPUs from 2018 onward, including the T4. Minimum VRAM for 4-bit QLoRA is 3.5 GB for 3B, 5 GB for 7B, 6 GB for 8B, 6.5 GB for 9B, 7.5 GB for 11B and 8.5 GB for 14B. A 4 to 8B model fits a free Colab T4 (16 GB) and an L4 (24 GB).
- The Gemma 3 guide confirms "Colab Notebooks with free Tesla T4 GPUs also work" and gives a 4B notebook and GGUF export (https://unsloth.ai/docs/models/tutorials/gemma-3-how-to-run-and-fine-tune).
- Typical time [unverified estimate]: 2,000 to 3,000 examples of about 500 tokens for 2 to 3 epochs take about 30 to 90 minutes for a 4B model and 1.5 to 3 hours for an 8B model on a T4. An L4 is roughly 1.5 to 2 times faster. A Cloud Run job with an L4 costs about 1 to 3 a run.

Dataset size for one author's voice [unverified, common practice plus Google's guidance above]. Start at 100 to 300 clean pairs to test whether tuning beats a good prompt. A stable voice usually needs 500 to 2,000 pairs of 300 to 800 words each, built as a brief or outline mapped to her finished passage. Hold out 10 percent for validation.

Known pitfalls.
- Overfitting: the model repeats her stock phrases and openings. Use 1 to 3 epochs, a low LoRA rank (8 to 16), a validation split and early stopping.
- Memorising private text: a tuned model can reproduce training passages word for word. Remove unpublished, personal or third-party sensitive material before training, deduplicate, and test by prompting with the first sentence of training passages.
- Style is not knowledge: tuning teaches voice, not facts. Keep retrieval for citations and claims.
- Lifecycle: a tuned Gemini model depends on its base model's retirement date [unverified]. An open-weights LoRA stays hers, but the base model licence applies (Gemma terms, Llama community licence, Apache-2.0 for most Qwen sizes) [unverified].
- Evaluation: compare against prompt plus retrieval in a blind test before paying for any serving path.

Cost table at about 300 generations a month. Assumptions: 1,500 output tokens each; 8,000 input tokens for (a) and 3,000 for (b). All rows are [inference] from the prices above.

| Option | One-off cost | Monthly cost | Notes |
|---|---|---|---|
| (a) Prompt plus retrieval, Gemini 2.5 Flash | 0 | About 1.85 | 2.4M input at 0.30 plus 0.45M output at 2.50 |
| (a) Same on Gemini 3.8 Flash, global | 0 | About 3.50 to 31 Dec 2026, about 7 after | Promotional price ends 31 December 2026 |
| (b) Gemini 2.5 Flash supervised tuning | About 15 per run (1,000 examples of 1,000 tokens, 3 epochs); 4.50 on 2.5 Flash-Lite | About 1.40 | Served at base price, no hosting fee listed |
| (b) Gemini 3.5 Flash tuned, Singapore endpoint | About 30 per run | About 8 | 1.5 times base price outside the global region |
| (c) LoRA on an open 4 to 12B model, Cloud Run L4, scale to zero | 0 on Colab T4, or 1 to 3 on an L4 job | About 5 if used in 10 sessions; about 10 if daily; up to about 90 if 300 separate wake-ups | 1.05 an hour; idle tail before scale-down is billed [idle window length unverified] |
| (c) Same as a monthly Cloud Run GPU batch job | As above | About 3 | Billed only while the job runs |
| Vertex AI endpoint, g2-standard-4 with L4, always on | 0 | About 593 | Cannot scale to zero |

## 6. Firestore vector search

Firestore (https://docs.cloud.google.com/firestore/docs/vector-search and https://docs.cloud.google.com/firestore/quotas, opened 2026-11-16).
- `findNearest` runs K-nearest-neighbour queries with EUCLIDEAN, COSINE or DOT_PRODUCT distance. Client libraries: Python, Node.js, Go and Java.
- Limits: "The maximum supported embedding dimension is 2048." "The maximum number of documents to return from a nearest-neighbor query is 1000 (Standard edition limitation only)." "The index type must be flat." Real-time listeners are not supported. Filtering before the search needs a composite vector index.
- Create the index with `gcloud firestore indexes composite create ... --field-config field-path=<field>,vector-config='{"dimension":"768","flat":"{}"}'`.
- Documents are limited to 1 MiB. The free tier is 1 GiB stored and 50,000 reads a day.
- Pricing: the vector search page states no cost. Firestore bills one document read per batch of up to 100 vector index entries scanned, plus normal reads for returned documents [unverified, pricing page not opened]. A query over 5,000 chunks is then about 50 to 60 reads, so about 800 queries a day stay free [inference]. 5,000 vectors of 768 dimensions are about 31 MB.

BigQuery vector search [unverified]. `VECTOR_SEARCH` works without an index by brute force, and a vector index needs at least 5,000 rows. On-demand queries cost 6.25 per TiB after 1 TiB free a month. Each query is a job with one to several seconds of latency, which suits batch analysis, not an interactive agent.

pgvector [unverified]. Cloud SQL for PostgreSQL supports the `vector` extension. At 5,000 rows an exact scan takes milliseconds and no index is needed. The marginal cost is 0 if the instance already exists and about 13 a month if it would be created only for this.

One-line recommendation. Use Firestore `findNearest` with 768-dimension embeddings: it is already in the stack, needs no new service and is free at this size. Choose pgvector only if the shared Postgres exists anyway and she wants SQL joins or keyword-plus-vector search in one query.

## 7. Resource hierarchy and project migration

Everything in this section is [unverified]: no page could be opened (see Method limit). It reflects Google's documentation as known to the model up to mid-2026.

Hierarchy.
- An organisation cannot contain another organisation. The organisation resource is the root node and maps one-to-one to a Google Workspace or Cloud Identity account.
- The supported pattern is folders under the organisation (nesting up to 10 levels) and projects under folders. For two ventures: one folder each, with separate projects for production and development.
- A Cloud Billing account belongs to an organisation but can pay for projects in any organisation. One billing account for everything is simplest. Use separate billing accounts when costs, credits or legal entities must stay apart.

Migrating projects between organisations later.
- Google documents this under Resource Manager, "Migrating projects between organisations". Project ID, project number and resources do not change, and there is no downtime in the move itself.
- IAM roles: Project Mover (`roles/resourcemanager.projectMover`) on the project and its current parent, and Project Creator (`roles/resourcemanager.projectCreator`) on the destination organisation, or Project Mover on the destination folder.
- Organisation policies: the source organisation must allow the destination in `constraints/resourcemanager.allowedExportDestinations`, and the destination must allow the source in `constraints/resourcemanager.allowedImportSources`. Setting them needs Organisation Policy Administrator on each side.
- What changes or breaks: IAM policies and organisation policies inherited from the old organisation stop applying and the new ones start; custom roles defined at organisation level do not move; organisation-level tags, log sinks and Security Command Center coverage do not follow; Shared VPC attachments and VPC Service Controls perimeters must be removed or re-planned first; grants to groups and users of the old organisation's domain keep working only if the new organisation's domain-restriction policy allows them.
- The project stays linked to its existing billing account after the move.

Changing a project's billing account. She needs Billing Account User (`roles/billing.user`) on the target billing account and Project Billing Manager (`roles/billing.projectManager`) or Owner on the project. The change is in Billing, Account management, Change billing. Services keep running. Usage before the change stays on the old account, and credits do not move with the project.

Credit programmes. Whether a credit programme's terms allow a given project is a question for the programme; no terms were reviewed here.

Cloud Identity Free for a second domain.
- Cloud Identity Free costs nothing and has a default limit of 50 users, which can be raised on request.
- A separate organisation needs a separate Cloud Identity or Workspace account with its own primary domain, verified by DNS.
- A domain can belong to only one account at a time. If the second domain is already a secondary or alias domain of the first account, it must be removed there first.
- Adding the second domain as a secondary domain of the existing account does not create a second organisation.

## 8. Per-agent-team credentials without key files

The pattern below is [unverified] in this session: the Cloud Run pages for service identity, secrets and access management exist in the Cloud Run docs navigation, but the fetches were refused.

Recommended pattern.
- One user-managed service account per Cloud Run service or agent team. Do not use the Compute Engine default service account. Cloud Run obtains short-lived tokens from the metadata server, so no key file exists.
- Least privilege at resource level: for example `roles/aiplatform.user` on the project for the gateway, `roles/pubsub.publisher` on one topic, `roles/bigquery.dataEditor` on one dataset, and `roles/datastore.user` narrowed with IAM Conditions where possible.
- Secret Manager: grant `roles/secretmanager.secretAccessor` on each individual secret to the one service account that needs it, never at project level. Mount secrets as environment variables pinned to a version, or as a volume when the service should pick up a rotated value without a redeploy.
- Service-to-service calls: `roles/run.invoker` on the target service and Google-signed ID tokens, with ingress set to internal where possible.
- CI: Workload Identity Federation with the Git host's OIDC token, an attribute condition on the exact repository and branch, and impersonation of a deploy service account. Set `constraints/iam.disableServiceAccountKeyCreation` so that no key file can be made.
- Humans and local development: impersonate the service account for short-lived tokens (one hour by default) through `roles/iam.serviceAccountTokenCreator`, not downloaded keys.
- Turn on Data Access audit logs for Secret Manager and alert on reads by unexpected principals.
- Cost: Secret Manager is about 0.06 per active secret version per month and 0.03 per 10,000 accesses [unverified]; the free tier is 6 active versions and 10,000 accesses a month (third-party summary, https://agentdeals.dev/gcp-free-tier-2026).

Third-party secrets that cannot be federated.
- General rule: one secret per credential per environment, each readable by exactly one service account. Rotation means adding a new version, checking it works, then disabling the old version. Secret Manager rotation schedules only publish a Pub/Sub reminder; the rotation code is hers.
- Stripe restricted keys: create one restricted key per service with only the resources it needs. Roll the key in Stripe with an overlap period, store the new value as a new version, then let the old key expire.
- Meta long-lived tokens: Instagram and Threads tokens last 60 days and are refreshable (opened pages, item 4). Run a Cloud Scheduler job every 30 to 45 days that calls the refresh endpoint and writes a new secret version. Alert if the refresh fails, because an expired token needs an interactive login.
- Substack session cookie [inference]: it is a full-account credential with no scopes and no official API. Keep it in its own secret readable by one publishing service only. Rotation is manual: log in again and store the new cookie. Log every use, and expect it to break without notice. It is the highest-risk secret of the three.
- Keep all three out of the LLM gateway's reach. The October 2026 LiteLLM incident harvested every credential the proxy process could read.

Google guidance on agent identity in 2026 [unverified]. Google introduced "agent identity" for agents deployed on Vertex AI Agent Engine, now under the Gemini Enterprise Agent Platform name: each agent gets its own IAM principal, in SPIFFE format, tied to the agent's lifecycle, so roles are granted to the agent and not to a shared service account. For agents on Cloud Run, as hers are, the equivalent control is still one service account per service. Check the IAM documentation for the current status before relying on it.

## Sources not opened and why

Refused by the fetch permission system (not retried):
- https://docs.cloud.google.com/resource-manager/docs/cloud-platform-resource-hierarchy
- https://docs.cloud.google.com/resource-manager/docs/project-migration
- https://docs.cloud.google.com/compute/docs/create-linux-vm-instance (redirect target of Google's free-tier compute page)
- https://docs.cloud.google.com/run/docs/securing/service-identity
- https://docs.cloud.google.com/run/docs/configuring/services/secrets
- https://docs.cloud.google.com/run/docs/securing/managing-access
- https://docs.postiz.com/llms-full.txt (Postiz public API reference)
- https://github.com/langfuse/langfuse-terraform-gcp (Terraform module README)

Failed at the site:
- https://cloud.google.com/blog/products/serverless/cloud-run-gpus-are-now-generally-available (blog error page; cold-start figure taken from the GPU docs and from https://www.infoq.com/news/2025/06/google-cloud-run-nvidia-gpu, which reports "under 5 seconds")
- https://developers.facebook.com/documentation/instagram-platform/content-publishing.md (the `/docs/` version of the same page was opened)

Never searched, because the search budget ran out: credit programme terms, Cloud Identity Free, Workload Identity Federation, Secret Manager rotation and pricing, IAM agent identity, BigQuery vector search, Firestore pricing for vector queries, AlloyDB Omni licensing, the LiteLLM LICENSE file, LiteLLM's own October 2026 incident report, the Unsloth Studio licence, and Compute Engine pricing in asia-southeast1.
