# Contracts for the Stage 1 launch track

**Status:** In force · version 0.4 · 2026-11-20 (0.2 was approved by merge on 2026-11-19; 0.3 records the owner's decisions: grant policies by plan interval, Substack plans recorded per interval, sign-in email from the platform's own domain; 0.4 adds `plan_interval` to `Reason`, the route kind `substack_change_plan`, `config/launch.substack_account_url` and the place of the legal texts)
**Design:** [launch track](../superpowers/specs/2026-11-19-launch-invites-grants-promotions-design.md) · [02](../architecture/02-membership-and-entitlements.md) · [09](../architecture/09-events-and-data-model.md)

A **contract** here is a name and a shape that two lanes of the build both rely on: an HTTP route, a Python function in a module's `public.py`, a Firestore document, an event, a setting. Lanes build against this page in parallel. **Changing anything on it is a pull request of its own, owned by the integrator, merged before the code that needs it.** Once the code exists, the Pydantic models are the source of truth and this page is regenerated from them.

## 1. Conventions

- JSON, `snake_case`. Timestamps are RFC 3339 in UTC. Ids are opaque strings.
- The browser never calls `platform-api`. `web` calls it with its service identity and forwards the member's session in the header `X-Member-Session`. Routes under `/v1/public/` need no member session.
- Routes under `/v1/admin/` are called by `platform-cli` with the owner's own Google identity token. The service reads the account id from the token and accepts it only if it is in `PLATFORM_OWNER_ACCOUNTS`. Every admin call, reads included, writes an audit entry naming that account.
- An email address appears in exactly one request body (`/v1/session/resolve` carries it inside the sign-in token) and in no response, log line or event. The account page shows `email_hint` (first character and domain).
- Errors: `{"error": {"code": "<code>", "message": "<plain words>", "retry_after": <seconds or null>}}`

| HTTP | `code` | Meaning |
| --- | --- | --- |
| 401 | `unauthenticated` | No valid member session |
| 403 | `forbidden` | Signed in, not allowed. `reason` is added for downloads: `paid_required`, `purchase_required` |
| 404 | `not_found` | Unknown id, or a route not served in this mode |
| 409 | `terms_required` | The member must accept the current terms first. Returned by every member route except `GET /v1/me`, `POST /v1/me/terms-acceptance`, `POST /v1/session/revoke` and `POST /v1/me/deletion-request` |
| 422 | `validation_failed` | Body did not match the shape |
| 429 | `rate_limited` | `retry_after` says when |
| 503 | `unavailable` | A source could not be reached; nothing was changed |

## 2. HTTP routes (`web` → `platform-api`)

| Route | Request | Response (200) |
| --- | --- | --- |
| `GET /v1/public/campaigns/{slug}` | – | `{slug, audience, state: "scheduled" \| "open" \| "closed", copy: {headline, body, cta}}`. Unknown slug: the default campaign with `slug: null`. The slug `default` is reserved and always returns the default campaign. While the `join_open` switch is off, every campaign's `state` is `closed` |
| `GET /v1/public/promotions/active` | – | `{promotions: [Promotion]}` for the `guests` audience. Cacheable for 60 seconds |
| `POST /v1/session/resolve` | `{id_token, campaign: <slug or null>}` | `{session: {cookie, expires_at}, member: Member, access: Access, join: Join}` |
| `POST /v1/session/revoke` | – | `{}` |
| `GET /v1/me` | – | `{member: Member, access: Access}` |
| `GET /v1/me/entitlements` | – | `{entitlements: [Reason]}` |
| `POST /v1/me/terms-acceptance` | `{terms_version, privacy_version}` | `{member: Member}` |
| `POST /v1/me/refresh-access` | – | 202 `{check: "fresh" \| "started" \| "already_running", last_completed_at, next_allowed_at}`. Starts the reconcile job unless one completed in the last 60 seconds. At most once a minute and six times an hour per member. `web` then polls `GET /v1/me` |
| `GET /v1/me/upgrade-options` | – | `{routes: [Route], promotion: Promotion or null}` |
| `POST /v1/me/support-requests` | `{kind: "paid_not_recognised" \| "other", note: <up to 500 characters>}` | `{id}` |
| `POST /v1/me/deletion-request` | – | `{status: "deletion_requested"}` |
| `GET /v1/library/items` | – | `{items: [ItemCard]}` |
| `GET /v1/library/items/{sku}` | – | `{item: ItemCard, description, citation}` |
| `POST /v1/library/items/{sku}/download` | – | `{url, expires_at}`; 403 with `reason` when not entitled |
| `GET /health` | – | `{status: "ok", service, mode, env}`, as in the S1.0 plan |

Admin routes (called by `platform-cli`):

| Route | Request | Response (200) |
| --- | --- | --- |
| `POST /v1/admin/contacts/search` | `{email}` in the body, never in the address | `{contact: ContactView or null}`: channels, entitlements with reasons, the audit entries that created them |
| `POST /v1/admin/entitlements` | `{email, grant, months or valid_until, reason}` | `{entitlement_id}` |
| `POST /v1/admin/entitlements/{id}/revoke` | `{reason}` | `{}` |
| `PUT /v1/admin/campaigns` · `PUT /v1/admin/promotions` | The validated contents of the configuration file | `{written: <n>}` |
| `PUT /v1/admin/launch` | `{join_open, library_open, promotions_open}` (any subset) | The stored switches |
| `GET /v1/admin/launch/report` | – | Counts per campaign and promotion |
| `GET /v1/admin/support-requests` | – | `{requests: [...]}` with `member_uid`, `kind`, `note`, `created_at` |
| `POST /v1/admin/library/publish` | `{staging_prefix, dry_run}` | `PublishReport` |

```jsonc
// Member
{"uid": "…", "display_name": null, "email_hint": "a…@example.org",
 "terms": {"accepted": true, "terms_version": "…", "privacy_version": "…", "required": {"terms_version": "…", "privacy_version": "…"}},
 "joined_via": "<campaign slug or null>", "status": "active"}

// Access: always computed, never stored
{"tier": "free" /* or "paid" */, "sections": ["overview", "library", "account"],
 "items": ["<sku>"], "reasons": [Reason], "computed_at": "…"}

// Reason: why the member holds something, in terms a person can read
{"grant": "tier:paid", "source": "substack_stripe" /* substack_roster | platform_stripe | payhip | grant */,
 "label": "substack_subscription" /* substack_status | launch_grant | owner_grant | purchase | platform_subscription */,
 "access_scope": "substack+platform", "status": "active", "valid_until": "…", "campaign": null,
 "plan_interval": null /* "month" or "year" when the source is a Substack subscription, else null */}
// A reader whose plan does not include the platform has tier "free" and one Reason with grant "status:substack_paid",
// label "substack_status" and the plan_interval of the plan they pay for. web uses it to say which plan they are on.

// Join: what happened at this sign-in
{"campaign": "<slug or null>", "recognition": "paid" /* or "free" */,
 "source_checked_at": "…", "check": "fresh" /* or "started": a reconcile was begun, poll GET /v1/me */,
 "grant": {"created": true, "valid_until": "…"} /* or null */}

// Route and Promotion
{"kind": "substack" /* or "platform_only", or "substack_change_plan": the member already pays Substack on a plan that
   does not include the platform; url is config/launch.substack_account_url, where they change the plan themselves */,
 "available": true, "url": "…"}
{"id": "…", "channel": "substack_offer", "plan_interval": "year", "starts_at": "…", "ends_at": "…",
 "url": "…", "display": {"badge": "…", "headline": "…", "body": "…"}}

// ItemCard
{"sku": "…", "title": "…", "kind": "guide", "abstract": "…", "version": "…", "pages": 0,
 "access": "paid", "can_open": true, "buy_url": null}
```

## 3. Module interfaces (`platform_api/<module>/public.py`)

Other modules and the HTTP layer use only these. Types are Pydantic models in the module's `models.py`.

| Module | Function | Notes |
| --- | --- | --- |
| `identity` | `resolve_session(id_token: str, campaign_slug: str \| None) -> SessionResult` | Verifies the token, upserts the member, then calls `entitlements.claim_for_member`, `entitlements.apply_grant_policies` and `entitlements.record_arrival`; asks `commerce.request_refresh` when the last reconcile is older than `reconcile_max_age_seconds` |
| | `member_from_session(cookie: str) -> MemberRef` | Raises `Unauthenticated` |
| | `accept_terms(uid, terms_version, privacy_version) -> Member` | |
| `entitlements` | `contact_id_for(email: str) -> str` | Keyed hash through Cloud KMS; the only place an email becomes an id |
| | `upsert_contact(email: str, channels: ChannelsPatch) -> str` | |
| | `plan_reconcile(existing: list[Entitlement], states: list[SourceState], guard: Guard) -> ReconcilePlan` | **Pure.** Applies Rules 2, 3 and 6. Creates, updates and ends strictly from what `states` say (a state with status `expired` ends its entitlement). An existing entitlement of the same source with no state in the run is left unchanged and listed in `plan.unseen`. Returns `blocked`, with nothing to apply, when the guard trips |
| | `apply_plan(plan: ReconcilePlan, run_id: str) -> ReconcileReport` | One transaction per contact. Compares `access_for` before and after for a contact that has a member and emits `membership.tier.changed` when the tier differs; then calls `apply_grant_policies` for that contact |
| | `claim_for_member(uid: str, contact_id: str) -> list[str]` | Rule 4 |
| | `access_for(uid: str, now: datetime) -> Access` · `can_open(uid: str, sku: str, now: datetime) -> Decision` | **Pure** over loaded entitlements; a `grant` past `valid_until` is not live |
| | `grant(contact_id, grant, valid_until, reason, actor) -> str` · `revoke(entitlement_id, reason, actor) -> None` | Audited |
| | `campaign_by_slug(slug: str \| None, now) -> Campaign` | Falls back to the default campaign |
| | `grants_due(entitlements: list[Entitlement], campaigns: list[Campaign], now) -> list[GrantSpec]` | **Pure.** The grant policy of the design, §5.4, over every open campaign that has one. Uses each entitlement's `valid_from` for `paid_since_before` and its `plan_interval` for `plan_intervals`; an entitlement without a plan interval never satisfies a policy that sets `plan_intervals` |
| | `apply_grant_policies(contact_id: str, now) -> list[str]` | Creates the grants that are due for a contact that has a member. Called at sign-in and from `apply_plan`. Idempotent |
| | `record_arrival(uid: str, campaign: Campaign, recognition: str) -> None` | Sets `joined_via` on first sign-in only; increments the campaign's counts |
| `commerce` | `stripe_reconcile(dry_run: bool) -> SyncRun` | Lists subscriptions, maps each to a `SourceState`, calls `plan_reconcile` and `apply_plan` |
| | `request_refresh(uid: str \| None, now) -> RefreshTicket` | Starts the `stripe-reconcile` job through the Cloud Run Jobs API unless one completed within the last 60 seconds or one is running. `platform-api` never reads the Stripe key |
| | `active_promotions(audience: Audience, now) -> list[Promotion]` · `upgrade_options(uid, now) -> UpgradeOptions` | |
| `library` | `catalogue(access: Access) -> list[ItemCard]` · `item(sku, access) -> ItemDetail` | |
| | `download_link(uid: str, sku: str, now) -> SignedLink` | Raises `NotEntitled(reason)`; logs the download |
| | `publish(manifest_dir: Path, dry_run: bool) -> PublishReport` | |

Refinements made when the Core plan was written (2026-11-20):

- **Time is passed in.** `resolve_session`, `accept_terms`, `plan_reconcile`, `apply_plan`, `grant` and `revoke` take a final argument `now: datetime`, like the functions above that already show one.
- **`plan_reconcile`** derives each state's contact id through the contact key and then calls the pure function `entitlements.reconcile.plan`.
- **`record_arrival`** updates the contact's `invite`, the campaign's counts and publishes `membership.campaign.joined`. `identity` stores `joined_via` on the member it creates, and calls `record_arrival` on the first sign-in only.
- **`apply_plan`** compares a member's tier before the plan with the tier after the plan and after the grant policies, and publishes at most one `membership.tier.changed` per member.
- **`entitlements.public.launch_config()`** returns the `config/launch` document. While `join_open` is off, a person with no member document cannot sign in (403 `forbidden`); an existing member can.
- **`identity`** also offers `end_sessions(uid)`, `member_view(uid)`, `request_deletion(uid, now)`, `file_support_request(uid, kind, note, now)` and `list_support_requests()`. `admin.public` offers the `owner` dependency that every `/v1/admin/` route uses.
- **`PUT /v1/admin/launch`** also takes `required_terms_version`, `required_privacy_version`, `reconcile_max_age_seconds` and `substack_account_url`.

```python
class SourceState(BaseModel):        # what a source says now about one grant for one person
    source: Literal["substack_stripe", "substack_roster", "platform_stripe"]
    source_ref: str                  # Stripe subscription id, or "roster"
    email: str                       # used only to compute contact_id; never stored on the entitlement
    grant: str                       # "tier:paid" or "status:substack_paid", chosen per plan interval by settings
    status: Literal["active", "grace", "expired"]
    started_at: datetime | None      # when the source says the paid period began; becomes valid_from. Never "first seen"
    valid_until: datetime | None
    plan_interval: Literal["month", "year"] | None
    access_scope: Literal["substack+platform", "platform_only"]
    provider_time: datetime
```

`packages/substack-desk` (imports nothing from the platform):

```python
class SubscriberRecord(BaseModel):
    email: str
    type: Literal["free", "paid", "comp", "gift", "group_seat", "founding", "lifetime"]
    plan_interval: Literal["month", "year"] | None
    paid_until: datetime | None
    since: datetime | None

class DirectoryListing(BaseModel):
    records: list[SubscriberRecord]
    complete: bool                   # false when the file is truncated: nothing is applied. A missing required column raises ExportHeaderError, which names it
    rejected_rows: int
    exported_at: datetime            # used as started_at for a row that has no date of its own

class SubscriberDirectory(Protocol):
    def list_paid(self) -> DirectoryListing: ...

class FileDirectory:                 # reads Substack's export file
    def __init__(self, path: Path) -> None: ...
```

## 4. Documents (Firestore, additions to [09 §2](../architecture/09-events-and-data-model.md))

| Collection | Fields |
| --- | --- |
| `campaigns/{slug}` (replaces `invite_waves`; the slug is the id and never changes) | `audience`, `opens_at`, `closes_at`, `is_default`, `grant` (`grant`, `months`, `starts`, `fixed_until`, `requires_live_source[]`, `paid_since_before`, `plan_intervals[]` or null) or null, `copy` (`headline`, `body`, `cta`), `counts` (`arrivals`, `recognised_paid`, `grants_created`), `updated_at`, `updated_by` |
| `promotions/{promotion_id}` | `channel`, `audience[]`, `plan_interval`, `starts_at`, `ends_at`, `substack_offer_url`, `stripe_coupon_id` (later), `display`, `counts` (`upgrades_in_window`), `updated_at`, `updated_by` |
| `support_requests/{auto}` | `member_uid`, `kind`, `note`, `status` (`open`, `done`), `created_at`. Zone 1; the note is never copied into an event or a log |
| `config/launch` | `join_open`, `library_open`, `promotions_open` (booleans), `reconcile_max_age_seconds`, `required_terms_version`, `required_privacy_version`, `substack_account_url` (the page of the publication where a subscriber changes their plan) |
| `members/{uid}` gains | `joined_via` (campaign slug), `terms_accepted.privacy_version` |
| `contacts/{contact_id}` changes | `invite` becomes `{campaign, state}`; `channels.substack.last_seen_in_roster` is written by every roster import |
| `entitlements/{entitlement_id}` clarifies | `valid_from` is the source's `started_at`. For an owner grant or a launch grant it is the moment of the grant. `plan_interval` (`month`, `year` or null) is stored from the source state. A grant whose name starts with `status:` unlocks no section and no item; it is listed in `reasons` so the Account page can explain it |
| `sync_runs/{auto}` gains | `kind` (`stripe_reconcile`, `roster_import`), `dry_run`, `state` (`running`, `completed`, `failed`), `guard` (`passed`, `blocked`), `unseen`, counts by action, `requested_by` (`schedule`, `member`, `owner`) |

## 5. Events (additions to [09 §4](../architecture/09-events-and-data-model.md))

| Type (after the prefix) | Published by | Key data |
| --- | --- | --- |
| `membership.campaign.joined` | M2 | `member_uid`, `contact_id`, `campaign` (slug), `recognition` |
| `membership.tier.changed` (existing) | M2 | Published from the first day; its email consumer arrives in the first slice after launch |
| `membership.support.requested` | M2 | `member_uid`, `kind`. Never the note |
| `membership.entitlement.granted` (existing) | M2 | For a launch grant: `source: "grant"`, `source_ref: "campaign:<slug>"` |
| `membership.member.registered` (existing) | M2 | `invite_wave` is renamed `campaign` |
| `commerce.reconcile.completed` | M14 | `run_id`, `kind`, `dry_run`, `guard`, counts |
| `commerce.promotion.upgrade_counted` | M14 | `promotion_id`, `contact_id`, `channel`, `source_ref` |
| `content.item.downloaded` | M12 | `member_uid`, `sku`, `version` |

## 6. Settings, jobs and commands

Settings are read by `Settings` with the `PLATFORM_` prefix. Values that identify accounts are set from Terraform variables that are never committed.

| Setting | Meaning |
| --- | --- |
| `PLATFORM_ENV`, `PLATFORM_APP_MODE`, `PLATFORM_GCP_PROJECT` and the other fields of `Settings` | As in the S1.0 plan, Task 1 |
| `PLATFORM_CONTACT_KEY` | Resource name of the key **version** of the Cloud KMS MAC key for `contact_id` (Terraform output `contact_key_name`) |
| `PLATFORM_STRIPE_KEY_SECRET` | Secret Manager name of the restricted, read-only Stripe key. Set only on the `stripe-reconcile` job |
| `PLATFORM_RECONCILE_JOB` | Resource name of the `stripe-reconcile` job, which `platform-api` may start |
| `PLATFORM_OWNER_ACCOUNTS` | Account ids allowed to call `/v1/admin/` |
| `PLATFORM_ROSTER_INBOX_BUCKET` | Restricted bucket where the owner places the export file; objects are deleted after seven days |
| `PLATFORM_STRIPE_SUBSTACK_APPLICATION` | The application id that marks a subscription as created by Substack |
| `PLATFORM_STRIPE_TEST_CHANNEL_METADATA` | Dev only. When true, a sandbox subscription with metadata `test_channel=substack` is classified as created by Substack, because a sandbox cannot reproduce another platform's application id. `Settings` refuses to start with this set when `PLATFORM_ENV` is `prod` |
| `PLATFORM_SUBSTACK_GRANT_MONTH`, `PLATFORM_SUBSTACK_GRANT_YEAR` | What a paying Substack reader on a monthly, respectively annual, plan is recorded as: `tier:paid` (the platform is included) or `status:substack_paid` (a status that unlocks nothing by itself and only satisfies a grant policy). A reader whose plan interval is unknown (a roster row with an empty plan: complimentary, gift, billed by Apple) is always recorded as `status:substack_paid`; the owner gives such a reader the paid tier with an owner grant after review. The owner's commercial decision; set on the reconcile and roster jobs from Terraform variables |
| `PLATFORM_LIBRARY_BUCKET` | Private bucket for library files |
| `PLATFORM_SESSION_TTL_DAYS` | Session cookie lifetime |

Settings of `web` (read on the server at request time; none is prefixed `NEXT_PUBLIC_`, because one image serves dev and prod):

| Setting | Meaning |
| --- | --- |
| `SITE_ENV` | `local`, `dev` or `prod` |
| `SITE_ORIGIN` | The site's own origin, used for the same-origin check and for the sign-in link's return address |
| `PLATFORM_API_URL` | Where `platform-api` is; also the audience of the identity token `web` sends |
| `PLATFORM_API_FAKE` | `1` replaces `platform-api` and sign-in with fakes built on the shared test people. Refused when `SITE_ENV` is `prod` |
| `IDENTITY_API_KEY`, `IDENTITY_AUTH_DOMAIN` | Identity Platform's public client values, from Terraform outputs `identity_api_key` and `identity_auth_domain` |
| `SIGNIN_SENDER_HINT` | Optional. The address sign-in emails come from, shown to the reader |

| Job (`platform-cli job <name>`) | Runs | Schedule |
| --- | --- | --- |
| `stripe-reconcile` | `commerce.stripe_reconcile(dry_run=False)` | Cloud Scheduler; the period is a Terraform variable, shortened while a campaign is open. Also started by `platform-api` on request |
| `roster-import` | Reads the newest object in the roster inbox, builds states for paid rows that have no live `substack_stripe` entitlement, plans and applies. Refuses to write unless the latest `stripe_reconcile` run completed and passed its guard in the last 24 hours | Started by the owner |
| `selfcheck` | As in S1.0 | On deploy |

| Owner command | Does |
| --- | --- |
| `platform-cli stripe reconcile [--dry-run]` | Starts the job and prints counts by action, the unseen list's size and the guard decision |
| `platform-cli roster import --file <csv> [--dry-run]` | Uploads the export to the roster inbox and starts the `roster-import` job |
| `platform-cli campaign apply --file <yaml>` · `platform-cli promo apply --file <yaml>` | Validates and writes campaigns and promotions |
| `platform-cli launch set --join-open true \| false` (and `--library-open`, `--promotions-open`) | The layer switches |
| `platform-cli launch report` | Counts per campaign and promotion; no emails |
| `platform-cli contact show --email-stdin` · `platform-cli grant create --email-stdin --grant tier:paid --months <n> --reason <text>` · `platform-cli grant revoke --id <id> --reason <text>` | The inspector at launch, through the admin routes. Each read and change is written to the audit log under the owner's account |
| `platform-cli support list` | Open support requests |
| `platform-cli library publish --dir <path> [--dry-run]` | As in [04](../architecture/04-content-library-and-search.md) |

## 7. Infrastructure names (Terraform outputs the other lanes read)

`platform_api_url`, `platform_hooks_url`, `web_url`, `library_bucket`, `library_staging_bucket`, `roster_inbox_bucket`, `contact_key_name`, `stripe_key_secret_name`, `reconcile_job_name`, `roster_import_job_name`, `identity_api_key`, `identity_auth_domain`, `auth_email_domain`. Sign-in emails are sent by Identity Platform from `auth_email_domain`, a domain of the platform with SPF, DKIM and DMARC records; neither `web` nor `platform-api` sends email in the launch track. Service accounts follow [08 §3](../architecture/08-security-identities-and-org.md). The reconcile job runs as its own service account, which alone may read the Stripe key. `platform-api`'s account may start that job and may not read the key. The owner's account may call `platform-api`, write to the roster inbox and the library staging bucket, and start the two jobs; it has no role on Firestore or on the contact key.

## 8. Fixtures every lane uses

Invented people at `example.org`, in `services/platform-api/tests/fixtures/people.py` and mirrored for the website in `apps/web/tests/fixtures/people.ts`:

| Name | Is | Used to test |
| --- | --- | --- |
| `ana` | Paid by card on Substack, annual, `started_at` before the cut-off | Recognition, launch grant |
| `bo` | Free subscriber | Free workspace, upgrade options |
| `cy` | Paid by card, monthly, `started_at` after the cut-off | No launch grant when `paid_since_before` is set; an upgrade counted in a promotion window |
| `di` | Complimentary, in the roster file only, no plan interval | Roster recognition as `status:substack_paid`: free workspace, no launch grant when the policy names plan intervals; paid only after an owner grant |
| `ed` | Pays with one address, signs in with another | The not-recognised route |
| `fay` | Was paid, cancelled; holds a launch grant | Grant keeps access; ends on its date; `membership.tier.changed` when it does |
| `gus` | Paid by card and also listed as paid in the roster file | The roster import creates nothing for him |
| `hal` | Paid by card, monthly, `started_at` before the cut-off | No launch grant when the policy sets `plan_intervals` to annual only; paid or free workspace according to `PLATFORM_SUBSTACK_GRANT_MONTH`; with `status:substack_paid`, the monthly-plan message and the `substack_change_plan` route |

**Legal texts.** The terms of use and the privacy notice are Markdown files in this repository, `apps/web/content/legal/terms.md` and `privacy.md`, each with front matter `version` (a date, `YYYY-MM-DD`) and `effective_from`. `web` renders them at `/terms` and `/privacy`. `config/launch.required_terms_version` and `required_privacy_version` name the versions a member must have accepted; the owner changes them with `platform-cli` after a new text is merged. The integrator drafts the texts; the owner approves them by merging.

A recorded Stripe subscription list (sandbox data, ids replaced) lives in `services/platform-api/tests/recorded/stripe/`. Tests never call Stripe or Substack.
