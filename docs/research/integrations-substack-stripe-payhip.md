# Integrations research: Substack, Stripe, Payhip, email (as of 2026-11-16)

Scope: Stage 1 of a member platform (Next.js + FastAPI on Cloud Run, Firestore, Google Identity Platform) for a Substack publication with a small paid readership. Read-only desk research.

Limits of this pass: the shared web-search budget ran out after about 20 searches, so Q7 (email pricing) and a few details rest on model knowledge and are marked [unverified]. Pages that could not be opened are listed at the end. Labels: [inference] = my reasoning from sources; [unverified] = not checked against a source in this pass.

## Answers table

| # | Question | Short answer | Confidence |
|---|---|---|---|
| 1a | Substack public API / webhooks / OAuth | No webhooks, no general API. Official surfaces are narrow: a Developer API for public creator profiles, and a read-only per-publication "Publisher API" (posts, stats, daily counts, lookup of one subscriber by email) that is not enabled for every publication | Developer API terms: confirmed by official docs. Publisher API, no webhooks, no Zapier app: reported by third parties |
| 1b | CSV export, RSS, welcome emails | CSV export of subscribers (no names; plan type and subscribe date by default, engagement columns in "all columns"). RSS at `/feed`. Separate editable welcome emails for free, paid, founding and imported subscribers | Confirmed by official docs (RSS item limits: third party) |
| 1c | Terms on automated access | Terms of Use prohibit anyone who "crawls," "scrapes," or "spiders" any page or data, "manual or automated", and reverse engineering | Reported by third parties (clause capture; official page could not be opened) |
| 2 | Own webhook endpoint on a Stripe account whose subscriptions Substack created | Yes in practice: the subscriptions are direct-charge objects that exist in her account, and an account-scope destination receives "Events from resources in your account". No doc sentence says it for platform-created objects in so many words; confirm with one call to list events | Confirmed by official docs (by composition) plus third-party practice |
| 2b | May she modify / cancel those subscriptions? | Technically yes (full-Dashboard accounts can manage their customers' subscriptions), but Substack expects changes through its own dashboard. Treat as read-only | Confirmed by official docs; desync risk is [inference] |
| 3 | Event destinations in 2026 | Webhook endpoints remain standard. Cloud bus options are Amazon EventBridge and Azure Event Grid only; nothing for Google Cloud. Test with sandboxes, test clocks, Stripe CLI | Confirmed by official docs |
| 4 | Payhip webhooks / API | Webhooks: `paid`, `refunded`, `subscription.created`, `subscription.deleted`, with product id, name, key, permalink, buyer email, price, fees. API covers only coupons and licence keys; no sales or products endpoints. All features on every plan | Confirmed by official docs |
| 4b | Payhip pre-filled email / redirect | Redirect after purchase: yes (store-wide or per product). Pre-filling buyer email: not documented. Custom `metadata[...]` on a direct checkout link is passed to the webhook | Confirmed by official docs (pre-fill absence: unverified) |
| 5 | How others verify paid Substack status | Stripe customer records, paid-subscriber CSV plus same Stripe account, Publisher API lookup by email, export diffs, unofficial private API | Reported by third parties |
| 6 | Leaving Substack later | Stripe subscriptions stay on her account and keep billing; the 10% application fee continues until removed (Substack support, or cleared via API after disconnect). Substack's own "Disconnect Stripe" button cancels and refunds everyone. Apple in-app subscribers cannot be moved | Confirmed by official docs (Stripe, Substack, Ghost) |
| 7 | Transactional email for about 2,000 recipients | Amazon SES is cheapest (about USD 0.10 per 1,000); Resend and Brevo have usable free tiers with daily caps. All need an authenticated sending domain | Unverified (pricing pages could not be opened) |

## 1. Substack: API, webhooks, export, RSS, welcome emails, terms

**Official Developer API (narrow).** Substack publishes "Substack Developer API Terms of Use", last updated January 8, 2026 (https://substack.com/api-tos). The data it covers is public creator information only: name, LinkedIn and social URLs, subscriber count, bestseller status, leaderboard recognitions, profile summary and URLs. Private or inferred information is excluded. Caching is allowed only as "reasonably necessary to support your application". Rate limits are "as determined by Substack in its sole discretion". A third-party write-up says the single endpoint looks up a public profile by LinkedIn handle and needs an approval form (https://dev.to/equinoxaifinancergb/does-substack-have-an-api-2026-and-what-you-can-actually-get-29il). It does not expose subscribers, paid status or post archives.

**Publisher API (your own publication, read-only).** Reported by third parties, not verified against Substack's own documentation in this pass:
- Base URL `https://publisher-api.substack.com/v1`; per-publication key generated in the publication dashboard; "If you don't see a Publisher API option there, it may not be enabled for your publication yet." (https://github.com/dkships/substack-publisher-mcp)
- Endpoints as wrapped by that project: list posts, get post, post stats, daily subscriber counts by type (paid, free trial, comp, gift, lifetime, founding), and lookup of one subscriber by email.
- A vendor summary dated October 2026 says the lookup returns membership type, expiry, first payment, next charge and a bounce flag, returns 404 for a non-subscriber, and that the API cannot list subscribers (https://www.newsletterapi.io/substack-api). [unverified against official docs]
- Consequence: if it is enabled for her publication, this is the cleanest official check for "is this email a paid subscriber, including comp, gift and Apple-billed ones". If it is not enabled, it does not exist for her.

**Webhooks, OAuth, Zapier.** The same vendor page states "As of October 2026 Substack has no webhook setting for subscriber or post events", that there is no Substack app on Zapier, and that an OAuth server exists only behind Substack's own MCP endpoint, with no public developer programme (https://www.newsletterapi.io/blog/substack-webhooks). It also reports a read-only official MCP server limited to admins of Bestseller publications. All third-party; the Substack help centre pages opened in this pass mention no webhook or integration setting.

**New-subscriber notification emails.** Reported: from about 18 to 20 March 2026 the free-subscriber notification no longer contains the subscriber's email address ("1 person has subscribed to your Substack"), so parsing notification emails is no longer a way to detect sign-ups (https://www.newsletterapi.io/blog/substack-new-subscriber-notification-no-email). Third party.

**CSV export (official).** Help article "How do I export my email list on Substack?" (https://support.substack.com/hc/en-us/articles/6314498343700-How-do-I-export-my-email-list-on-Substack):
- Subscribers page, three dots, Export; all subscribers, a filtered list, or ticked rows.
- Two shapes: "All columns" ("These columns can vary from when the subscriber last opened an email to their individual post views") or visible columns only ("the default columns (such as the date someone subscribed and their type of plan)").
- "It's not currently possible to export a file with subscriber names."
- Dashboard columns documented (https://support.substack.com/hc/en-us/articles/360058529871-How-do-I-use-the-subscriber-dashboard-on-Substack): subscription type ("free, paid, founding, gift, or comp", with monthly or annual), activity, revenue (total paid, excluding refunds), email opens over 7 days, 30 days and 6 months, subscription source (free), paid upgrade date. Filters include start date, activity level, paid status, tags, country.
- An explicit expiry column is not confirmed by these two articles. The older settings export is commonly described as having `email, active_subscription, expiry, plan, email_disabled, created_at, first_payment_at` [unverified, model knowledge]. Check one real export before designing the importer.
- The export is a manual download. No official scheduled or API export was found.

**RSS (official).** "You can find the RSS feed for your publication at https://your.substack.com/feed." (https://support.substack.com/hc/en-us/articles/360038239391-Is-there-an-RSS-feed-for-my-publication). Third-party observation: about 20 most recent posts, free posts in full, paid posts cut at the paywall. No official RSS for Notes was found [unverified].

**Welcome emails (official).** Four templates: free, paid, founding, imported. Edited in Settings, Emails, "Edit the email template with your own content and click "Save"." Only for publications, and the paid and founding ones apply once payments are enabled (https://support.substack.com/hc/en-us/articles/24034796625428-How-do-I-set-up-welcome-emails-on-Substack). The article suggests linking to posts and adding a button, so a link to the member platform in the paid welcome email is within normal use.

**Terms.** The official Terms of Use page could not be opened in this pass. A clause tracker records, from the Terms of Use at https://substack.com/tos (document dated Oct. 6, 2026; clause captured June 28, 2026), a prohibition on anyone who:
- "Crawls," "scrapes," or "spiders" any page, data, or portion of Substack (through use of manual or automated means)" (https://conductatlas.com/platform/substack/substack-terms-of-use/provision/CA-P-029302/prohibition-on-scraping-or-crawling-substack/)
- "Decompiles, reverse engineers, or otherwise attempts to obtain the source code or underlying ideas or information of or relating to Substack." (https://conductatlas.com/platform/substack/substack-terms-of-use/provision/CA-P-029308/prohibition-on-reverse-engineering-substack/)

Reading: automated calls to the undocumented dashboard endpoints with a session cookie fall inside the scraping clause on its face, even for one's own publication [inference]. Enforcement against a publisher reading her own data is not documented either way. The Publisher Agreement (last updated July 20, 2026, https://substack.com/pa) says "you are the controller of your List", which supports exporting and using the list, but does not license automated access.

## 2. Stripe Connect: her own webhooks on an account where Substack created the subscriptions

**Do her own endpoints get the events?** Official statements that combine to yes:
- Connect webhooks doc (https://docs.stripe.com/connect/webhooks?accounts-namespace=v1): "Direct charges: The payment, refunds, and disputes exist on the connected account". The scope table lists "Updates to Invoices and Subscriptions that connected accounts charge their customers using direct charges" as resources of the connected account.
- Webhooks doc (https://docs.stripe.com/webhooks.md): when creating a destination, "Select **Your account** to listen to events from your own account", defined as "Events from resources in your account."
- OAuth doc for Standard accounts: objects a platform creates for an account, such as charges, customers and invoices, "will be visible on their Stripe account" (https://edge-docs.stripe.com/connect/oauth-standard-accounts).
- The facts already confirmed on her account (subscriptions readable with her own key, `application` set to Substack's id) are consistent with this.

What was not found: a sentence stating outright that an account-scope endpoint receives events for objects a platform created. Third parties build on exactly this (Sidestack "keeps your subscribers in sync through your Stripe customer records", https://sidestack.io; a 2026 vendor guide recommends a webhook endpoint on the writer's own Stripe account for `customer.subscription.created`, `customer.subscription.deleted`, `invoice.payment_failed`). Cheap proof before building: list recent events with her own key (for example type `customer.subscription.updated`). Events that appear in her account's event log are the ones her endpoint would be sent [inference].

**Caveats.**
- API version. For snapshot destinations you pick the API version, and "The Event sent to the destination is structured for the event destination's specified version", regardless of the version Substack used. Pin the endpoint version and the SDK version together. Per-item `current_period_end` (already observed) is the newer shape; older versions put it on the subscription [unverified, model knowledge].
- Delivery. Retries "for up to three days with an exponential back off in live mode"; manual resend up to 15 days in the Dashboard and 30 days by CLI; order is not guaranteed; duplicates happen ("logging the event IDs you've processed"). Up to 16 event destinations per account.
- Verification. `Stripe-Signature` header, HMAC SHA-256 over timestamp plus raw body with the `whsec_` secret; libraries default to a 5 minute tolerance. Stripe also recommends IP allowlisting.
- Identifying Substack objects. Use `application` on the subscription or charge and the `substack: yes` price metadata. `application` is not something a sandbox can reproduce, so make the classifier configurable [inference].
- Platform-controlled accounts. If an account is administered by a platform, Stripe support "strongly recommend[s] creating a new Stripe account" for a separate integration and advises against using API keys on it (https://support.stripe.com/questions/platform-administered-stripe-accounts). Her account has two platforms connected (Substack and Payhip), which suggests it is an ordinary owner-controlled account [inference]; confirm in Stripe settings.
- Substack's own guidance recommends a Stripe account used only for Substack, quoting Stripe's rule about "separate Stripe accounts for projects, websites, or businesses that operate independently" (https://support.substack.com/hc/en-us/articles/4405482746132-How-do-I-set-up-my-Stripe-account-on-Substack-to-start-receiving-payments). Native sales for the same publishing business on the same account look consistent with that rule [inference].

**May the account modify or cancel platform-created subscriptions?** Stripe: "Only connected accounts with access to the full Stripe Dashboard can manage their customers' subscriptions" and "Your platform can't update or cancel a subscription that another platform created" (https://docs.stripe.com/docs/connect/subscriptions). So she can, and no other connected platform can. Substack routes cancel, refund and auto-renew changes through its Subscribers tab and mentions the Stripe dashboard only for removing payment details (https://support.substack.com/hc/en-us/articles/6652618789396-How-do-I-make-changes-to-a-reader-s-subscription-on-Substack); it also warns "Do not disconnect your Stripe account directly from the Stripe dashboard." Changes made directly in Stripe may leave Substack's own records out of step [inference]. The platform should never write to these objects.

**Restricted keys.** "A RAK can do only what you give it permission to do"; per resource the choice is Read, Write or None; GET maps to read; "All Stripe APIs support restricted API keys" (https://docs.stripe.com/keys/restricted-api-keys). No rule was found that limits a restricted key from reading objects created by a Connect application [inference: permissions are per resource, not per creator]. Suggested read-only set for this platform: Customers, Subscriptions, Invoices, Charges and Refunds, PaymentIntents, Products, Prices, Events, Balance and balance transactions (for fees and net), Payouts, Disputes; everything else None. Permission names should be checked in the Dashboard [unverified]. Create the webhook destination by hand in the Dashboard so the key needs no write permission.

## 3. Stripe event destinations and testing

- Webhook endpoints are still the standard. "Event destinations" is the umbrella term; types are webhook endpoint, Amazon EventBridge and Azure Event Grid ("You can also consume Stripe events in your AWS or Azure infrastructure"). No Google Cloud Pub/Sub or Eventarc destination is documented, so on Cloud Run the route is an HTTPS endpoint that verifies, stores the event id, returns 2xx and processes asynchronously (Cloud Tasks or Pub/Sub behind it is her own plumbing) [inference].
- Two payload formats: thin (recommended for new integrations; fetch the object after the notification) and snapshot (full object, needed if you want `previous_attributes` without another call). Managed in Workbench, Webhooks tab, or the v2 Event Destinations API (https://docs.stripe.com/workbench/event-destinations).
- Sandboxes: separate environments with their own keys and endpoints ("You must define separate webhook endpoints for your sandbox accounts"); sandbox deliveries retry "three times over the course of a few hours".
- Test clocks (https://docs.stripe.com/billing/testing): "Use test clocks to advance simulated time in a sandbox"; advance "up to two subscription intervals at a time"; Dashboard simulation is disabled for a customer with more than three subscriptions; list endpoints omit test-clock objects unless filtered by customer, subscription or clock. Covers renewals, trial end, failed renewal payment and cancellation.
- Stripe CLI: `stripe listen --forward-to ...` and `stripe trigger <event>` for handler tests; fixture events do not correspond to real subscriptions.
- Search API can look up customers by email, but "Don't use search for read-after-write flows"; data is usually searchable in under a minute (https://docs.stripe.com/search). Use list calls for anything that must be current.
- A read-only Queries and Reports API over the Sigma-style tables exists (https://docs.stripe.com/data/api) and could feed the revenue view; whether it needs a paid Sigma plan was not checked [unverified].

## 4. Payhip

**Webhooks (official, https://help.payhip.com/article/115-webhooks).**
- Setup: Settings, Developer tab, paste endpoint URL (several allowed, comma-separated), tick events. No plan requirement stated; the pricing page says every plan has "All features" and "no feature-gating here!" (https://payhip.com/pricing).
- Events: `paid`, `refunded`, `subscription.created`, `subscription.deleted`.
- `paid` payload: `id` (transaction id), `email`, `currency`, `price` (in cents), `vat_applied`, `ip_address`, `items[]`, `payment_type`, `stripe_fee`, `payhip_fee`, `unconsented_from_emails`, `is_gift`, `date`, `type`, `signature`.
- Each item: `product_id`, `product_name`, `product_key`, `product_permalink`, `quantity`, `on_sale`, `used_coupon`, `used_social_discount`, `used_cross_sell_discount`, `used_upgrade_discount`, `promoted_by_affiliate`, `has_variant`.
- `refunded` adds `amount_refunded`, `date_refunded`, `date_created`, and a `license_key` per item; equal to `price` means a full refund.
- Subscription events: `subscription_id`, `customer_id`, `status`, `customer_email`, `plan_name`, `product_name`, `product_link`, `gdpr_consent`, `date_subscription_started`, names, and `date_subscription_deleted` on deletion.
- Not in the documented payload: the coupon code itself (only a boolean), buyer name on `paid`, checkout-question answers.
- Verification: the `signature` field equals `hash('sha256', $apiKey)`. It is a static value derived from the API key, not a signature over the body, and the examples show the same value on every event. It proves the sender knows the key, not that the body is untampered or fresh [inference].
- Delivery: expects HTTP 200; otherwise retries "once an hour for up to 3 hours". Missed events are then gone, and there is no API to list sales.

**API (official, https://payhip.com/api-reference and https://help.payhip.com/article/347-public-api).** "We have an API available for managing coupons and license keys." Coupons: `POST /api/v2/coupons`, `GET /api/v2/coupons`, `GET /api/v2/coupons/:id` with header `payhip-api-key`. Licence keys: `GET /api/v2/license/verify`, `PUT /api/v2/license/disable`, `/enable`, `/usage`, `/decrease` with header `product-secret-key`. No sales, orders, customers or products endpoints; "more will be added in future". Rate limits not documented.

**Fees (official pricing page).** Free Forever: USD 0 per month, 5% per transaction. Plus: USD 29, 2%. Pro: USD 99, no Payhip fee. On all plans "PayPal and Stripe will still charge at their standard rates". At her volume the free plan is the cheapest until guide sales pass roughly USD 970 a month (break-even reported by a competitor's article, https://sellfy.com/blog/payhip-pricing/).

**Links, buttons, redirect.**
- Direct checkout link: `https://payhip.com/buy?link=PRODUCT_KEY`; several products with `cart_links[]=...`; and `metadata[key]=value` pairs (up to 20; keys up to 40 characters, values up to 500) which are "passed to your webhook payload" (https://help.payhip.com/article/126-direct-checkout-link). No parameter for pre-filling the buyer's email, a coupon or a quantity is documented.
- Checkout redirect: Settings, Advanced Settings, Checkout Settings, "Add success redirect", for all products or one product, to any http(s) URL. Buyers of digital products then "won't be able to instantly download them" and must use the emailed link. No query parameters on the redirect are documented (https://help.payhip.com/article/97-checkout-redirect).
- Custom checkout questions exist; answers appear in the Customers CSV export ("Checkout Responses" column). Payhip itself advises using them only if essential (https://help.payhip.com/article/128-custom-checkout-questions).
- Embed button and embedded product page from the product's share options [unverified, model knowledge; no help article was reached].
- Zapier: triggers only (New Sale, Sale Refund, New Membership Subscription, Cancel Membership Subscription, New Product) (https://help.payhip.com/article/116-zapier).

## 5. How others verify "is this person a paid Substack subscriber?"

1. **Stripe customer records on the writer's own account.** Sidestack (Discord access for Substack subscribers) has the writer connect Stripe, sends each subscriber a unique link to attach their Discord account, and tracks "subscription changes and cancellations" (https://sidestack.io, https://sidestack.io/articles/how-to-create-an-exclusive-discord-community-for-your-substack-subscribers). Same idea as this platform's plan.
2. **Paid-subscriber CSV plus the same Stripe account.** Ghost's Substack migrator: "Download paid subscribers from Substack", upload the CSV, and connect the same Stripe account so billing continues (https://docs.ghost.org/migration/substack). Outpost documents the same sequence for Ghost sites (https://documentation.outpost.pub/faq/migrating-to-outpost).
3. **Publisher API lookup by email**, where enabled (section 1). Third-party description only.
4. **Periodic export diff.** Compare each export with the previous one to find joiners and leavers; suggested as the fallback for free subscribers now that notification emails carry no address (https://www.newsletterapi.io/blog/substack-new-subscriber-notification-no-email).
5. **Unofficial private endpoints with a session cookie**, or no-code flows built on Gmail and Make (https://cloudnativecreator.substack.com/p/substack-subscribers-automation-part-3, method behind a paywall). Works until Substack changes its front end, and sits inside the scraping clause [inference].

Common to all: identity is established by control of an email address. None of them can see Apple-billed, comp or gift status through Stripe alone.

## 6. Moving members and leaving Substack

- **Inviting members now.** Paid welcome email is editable (section 1); posts can be sent to paid subscribers only (the Publisher API wrapper shows an `audience` value of `only_paid` on posts; paid-only posting is a core Substack feature [unverified in this pass]); paid subscribers can be filtered and exported.
- **Stripe subscriptions on exit (official Stripe).** "Subscriptions aren't automatically canceled when you disconnect from the platform." For direct charges: "After disconnect, subscriptions continue to run on the connected account. If the subscription was created with an application_fee_percent, the application fee continues to be collected by the platform after disconnect." And: "After disconnect, a connected account can clear the application_fee_percent parameter from existing Subscriptions through the API." (https://docs.stripe.com/docs/connect/subscriptions)
- **Substack side (official).** "Disconnect Stripe" in the Danger Zone will "Cancel all paid subscriptions to your newsletter", "Refund and notify all your paid subscribers by email" and "Revoke Substack's access to your Stripe account". For a move to another platform the article says to contact support through the support widget instead (https://support.substack.com/hc/en-us/articles/360060408872-How-do-I-turn-off-paid-subscriptions-on-Substack).
- **The 10% fee.** Ghost: "Substack will continue to take 10% fees on your existing paid subscriptions", with Ghost's concierge offering help. Outpost and a 2025 creator guide both say to email Substack and ask them to release the fee (https://lexroman.substack.com/p/how-to-leave-substack-in-10-easy). Members do not re-enter cards because the subscriptions and payment methods already live on her Stripe account.
- **Apple in-app subscriptions (official, https://on.substack.com/p/in-app-payments-iap-faq and https://support.substack.com/hc/en-us/articles/19718129670420-Can-my-subscribers-pay-on-the-Substack-iOS-app).** Since August 2025 new subscriptions bought in the iOS app are billed by Apple. Publishers cannot opt out. "Apple pays Substack monthly, typically up to 45 days after the end of the month", and Substack deposits earnings to the Stripe account. The publisher gets the subscriber's email and payment history but not the payment method. If the publisher leaves, Apple does not transfer the billing relationship. The articles do not say these subscribers appear as Stripe subscription objects; since Apple manages the subscription, assume they do not [inference].
- **Other.** Statement descriptors may still read "Substack" after a move; update in Stripe public details (Ghost docs).

## 7. Transactional email for a small platform on Google Cloud

All figures below are [unverified]: the providers' pricing pages could not be opened and no search budget remained. They reflect model knowledge to about mid-2026 and must be checked before a decision.

| Provider | Free tier (as recalled) | First paid step (as recalled) | Own sending domain with SPF/DKIM |
|---|---|---|---|
| Resend | 3,000 emails per month, 100 per day, 1 domain | about USD 20 per month for 50,000 | Required to send to real recipients |
| Brevo | 300 emails per day | about USD 9 per month for 5,000 | Required in practice (unauthenticated senders are rewritten) |
| Postmark | 100 emails per month (test tier) | about USD 15 per month for 10,000 | Required (DKIM and return-path) |
| Mailgun | 100 emails per day | about USD 15 per month for 10,000 | Required (sandbox domain only reaches authorised recipients) |
| Amazon SES | No lasting free tier; about USD 0.10 per 1,000 emails | Pay as you go | Required, plus a request to leave the SES sandbox |
| SendGrid | Free plan withdrawn in 2025; 60-day trial at 100 per day | about USD 19.95 per month | Required for good delivery (domain authentication) |

Notes: Gmail and Yahoo require SPF or DKIM for every sender and SPF, DKIM and DMARC above about 5,000 messages a day; publish all three anyway. Outbound port 25 is blocked on Google Cloud, so use the provider's HTTPS API from Cloud Run [unverified, model knowledge].

One-line recommendation: lowest cost is Amazon SES (about USD 0.20 to reach 2,000 people); lowest effort at zero cost is Resend's free tier for the steady trickle, with the first 2,000-recipient announcement sent as a normal Substack post rather than through the platform, because every free tier has a daily cap [inference].

## Design consequences

1. **Source of truth for Substack paid status is her own Stripe account.** A member is paid if a subscription created by Substack's application (and carrying the `substack: yes` price metadata) is `active` or `trialing` for a customer whose email matches the member's verified email. Entitlement end is the item-level `current_period_end`.
2. **Downgrade is event-driven with a daily safety net.** Handle `customer.subscription.created`, `.updated`, `.deleted`, `invoice.paid`, `invoice.payment_failed`, `charge.refunded` on an account-scope destination; keep access until period end when `cancel_at_period_end` is set; remove it on `deleted` or a terminal status. Reconcile every night by listing subscriptions, because retries stop after three days and order is not guaranteed. A short grace on `past_due` is a product choice [inference].
3. **Prove the webhook path first.** One read of recent events with her key shows whether Substack-created subscription events exist in her account log. If they do not, fall back to polling the subscriptions list every few minutes, which is fine at about 40 subscriptions [inference].
4. **Stripe does not see every paid member.** Apple in-app subscribers, comps, gifts (the buyer is the Stripe customer, not the reader) and any lifetime grants need another source. The platform needs a manual "entitlement override with expiry" table fed from Substack.
5. **What the Substack CSV (or Publisher API, or private API) is needed for:** the free-subscriber allow-list if joining is restricted to subscribers; plan type for the cases in point 4; tags and engagement columns if wanted. Nothing in Stage 1's paid flow for web subscribers depends on it.
6. **Prefer the Publisher API if her publication has it.** Check the dashboard for a Publisher API option. A lookup by email at sign-in would cover free, comp, gift and Apple-billed members officially. If absent, use a scheduled manual CSV upload (weekly is enough at this size) and keep any private-endpoint automation as a clearly labelled, switchable fallback given the terms.
7. **Never grant on an unverified email.** Identity Platform must verify the address (email link or a provider that asserts a verified email). Add a "my Substack email is different" flow that sends a confirmation link to the second address and stores it as an alias. Compare case-insensitively; do not strip dots or plus tags [inference].
8. **Onboarding route:** a link in the paid welcome email and in a paid-only post, plus one in the free welcome email. The link carries no secret; access comes from the verified email matching Stripe or the override table.
9. **Payhip purchases: the webhook is the only machine-readable record of which guide was bought.** Stripe's PaymentIntent has the email and amount but no product. Store `id`, `email`, `items[].product_key` and `product_id`, map product keys to guides, and revoke on a full `refunded` event.
10. **Close the email-mismatch gap on Payhip with metadata.** Send logged-in members to `https://payhip.com/buy?link=KEY&metadata[uid]=<member id>` so the webhook names the member even when they type a different email at checkout. Emails cannot be pre-filled. Set the success redirect back to the platform; the PDF still arrives by email from Payhip.
11. **Treat the Payhip webhook as weakly authenticated.** The signature is a constant. Use an unguessable endpoint path, compare the signature in constant time, de-duplicate on transaction `id`, and optionally confirm a matching Payhip-application PaymentIntent (email in `description`, amount, time) in Stripe before unlocking [inference].
12. **Payhip has no catch-up API.** Three hourly retries, then silence. Back-fill history and repair gaps from the Customers CSV export, and from Stripe PaymentIntents where the application is Payhip's. PayPal-paid orders, if PayPal is enabled, never appear in Stripe; `payment_type` in the webhook distinguishes them.
13. **One revenue view comes from Stripe plus a Payhip overlay.** Classify every charge by `application`: Substack's id, Payhip's id, or none (native). Take gross, fees and net from balance transactions. Add Payhip's `payhip_fee` and product names from webhooks. Show Apple in-app earnings as a separate line; they arrive as monthly deposits up to 45 days late, not per-subscriber charges.
14. **Stay read-only on Stripe.** Use a restricted key with read permissions only; never update, cancel or refund Substack-created objects from the platform; never disconnect Substack from inside the Stripe dashboard.
15. **Exit path is already paved.** Subscriptions and cards live on her account. When she leaves: ask Substack support to disconnect without cancelling and to release the fee, or clear `application_fee_percent` herself after disconnect; do not press "Disconnect Stripe" in Substack; expect to lose Apple-billed subscribers unless they re-subscribe. Until then the 10% applies to every Substack-created renewal.

## Sources that could not be opened in this pass

Blocked by a fetch permission prompt that nobody was present to answer; not retried:
- https://substack.com/tos (official Terms of Use; clause text above comes from a third-party capture)
- https://publisher-api.substack.com/v1/docs/ (Publisher API documentation)
- https://docs.stripe.com/billing/testing.md (same content later obtained through Stripe's documentation search)
- https://resend.com/pricing and https://www.brevo.com/pricing/ (and, by extension, the other email pricing pages, which were not attempted)

Not searched because the search budget ran out: Substack's help article on its MCP server, Circle and Memberful guides for Substack members, Beehiiv's Substack migration guide, Payhip's embed-button help article, and all email provider pricing.
