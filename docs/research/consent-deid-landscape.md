# Consent management and de-identification: what already exists (for module M2)

Date: 2026-11-16. Scope: open-source and commercial tools that overlap with "M2 Identity, consent and pseudonymisation".

How to read this file. A claim with no tag was read on a page listed under Sources. `[unverified]` means it comes from memory and was not opened today. `[inference]` means it is my judgement. This describes tools and standards. It is not legal advice.

Limits of this pass. The shared web-search budget ran out about two thirds of the way through. Sections 1 to 3 are mostly verified. Section 4 (commercial baseline and pricing) is almost entirely `[unverified]`. GA4GH Passports, Sage Bridge, Google Sensitive Data Protection pricing and Kantara's own pages were also not opened. Several GitHub pages were blocked by an unanswered permission prompt (listed at the end).

## Summary table

| Tool | Category | Licence | Stack / weight | API? | Fit for her module |
|---|---|---|---|---|---|
| gICS (Greifswald) | Research consent service | AGPLv3 | Java EE app server + MySQL, docker-compose, web UI | SOAP; FHIR through the TTP-FHIR Gateway | Copy the data model. Too heavy to adopt. |
| gPAS (Greifswald) | Pseudonym service | AGPLv3 | WildFly + MySQL | SOAP; FHIR through gateway | Copy the "domain" idea. Too heavy. |
| E-PIX (Greifswald) | Identity list and record linkage | AGPLv3 | Java app server + database | SOAP; FHIR through gateway | Not needed. She has logins, not error-prone patient demographics. |
| Mainzelliste (Mainz) | Pseudonymisation + record linkage | AGPL-3.0-or-later | Java .war on a web server + database | REST | Mature, but hospital-registry shaped. Skip. |
| ACE (2025) | Pseudonym service | "Permissive" (name not stated) | Java 21 Spring Boot + PostgreSQL + Keycloak, Docker | REST only, no GUI | Closest lightweight pseudonym API. No consent. |
| PEP / PaaS (Radboud) | Polymorphic pseudonymisation | Apache-2.0 (paas-api) | Rust server, TypeScript and Rust clients | REST | Stronger cryptography, early stage. Watch. |
| miracum vfps, fhir-pseudonymizer | Pseudonym service, FHIR pseudonymiser | Not confirmed | C# services, both updated in the last two months | fhir-pseudonymizer is REST; vfps not confirmed | FHIR-centric. Skip. |
| OpenPseudonymiser | Desktop salted-hash tool | Not stated | Desktop app | None | Same primitive as hers, no service. |
| CTRL (Australian Genomics) | Dynamic consent portal | Called open source; licence not stated | Ruby on Rails + PostgreSQL | Bi-directional APIs with REDCap | Borrow participant-facing ideas. |
| Consent2Share | Patient consent (US) | Apache-2.0 | Many Java services + HAPI FHIR | REST | Dormant since 2018 to 2020. Skip. |
| REDCap eConsent | Data capture + eConsent | Proprietary, free to non-profits | PHP/MySQL, self-hosted by the institution | Yes [unverified] | Not open source. What a university already has. |
| Sage Synapse / Bridge | Data repository / mobile study backend | Synapse Apache-2.0; Bridge [unverified] | Java on AWS, hosted by Sage | REST | Bridge is the closest conceptual analogue [unverified]. Not lightweight. |
| ResearchKit, SpeziConsent | Mobile consent screens | BSD; MIT | iOS client libraries | No backend | Interface only. |
| OpenClinica Community | Clinical data capture | LGPL | Java web app [unverified] | Not confirmed | Participant features are in the paid cloud product. Skip. |
| LimeSurvey, formr | Survey tools | GPL [unverified]; open source | PHP + MySQL; formr adds OpenCPU (R) | Yes [unverified] | No consent ledger. Anonymous mode is all or nothing. |
| RUDY (Oxford) | Dynamic consent study platform | Licensed through Oxford University Innovation | Not stated | Not stated | Not open. |
| Right Consents, c15t | GDPR and cookie consent | Open source; c15t Apache-2.0 | docker-compose + Keycloak; JS framework | Not confirmed | Different problem (web and marketing consent). |
| ClinConNet, ConInSe | Blockchain consent prototypes | Not stated | Proof of concept | n/a | Research prototypes only. |
| FHIR Consent (R5 / R4) | Standard | HL7 | n/a | n/a | Use as the export format. |
| ISO/IEC TS 27560:2023 | Standard (consent records and receipts) | ISO, paid text; open DPV guide | n/a | n/a | Use its field names in the ledger. |
| GA4GH DUO | Ontology of data-use terms | CC BY 4.0 | n/a | n/a | Tag every data release. |
| ARX | Tabular anonymisation | Apache-2.0 | Java desktop GUI + Java library | Java API | Reference tool. Use offline for hard cases. |
| pyCANON | Anonymity-level checker | Apache-2.0 | Python library + CLI | Python | Embed as the release gate. |
| ANJANA | Anonymiser | Apache-2.0 | Python library | Python | Embed to generalise or suppress up to k. |
| sdcMicro | Disclosure control for survey microdata | GPL-2 | R package + GUI | R | Most survey-specific. Run offline. |
| Amnesia (OpenAIRE) | k- and km-anonymity | Open source (licence not named) | Desktop app + browser demo | Not mentioned | GUI for researchers. Not embeddable. |
| Presidio | PII detection in free text, images, tables | MIT | Python packages, Docker REST service | REST (no built-in auth) | Embed for free-text answers. |
| Google Sensitive Data Protection | Managed DLP | Commercial | GCP API | REST | k-anonymity risk jobs on BigQuery [unverified]. Optional. |
| OpenDP, SmartNoise SQL, Tumult Analytics | Differential privacy | MIT; MIT; Apache-2.0 | Rust + Python; Python; Spark | Python | For public aggregate statistics, not microdata. |
| PPRL (R), anonlink/clkhash, ONS toolkit, Splink | Record linkage | GPL-3; Apache; not stated; MIT | Libraries | n/a | Only if she later links to outside datasets. |
| Datavant and similar | Commercial tokenisation | Proprietary | SaaS | Yes | Baseline only. No public pricing. |

## 1. Consent management tools

**gICS** is the most complete open research consent service found. Its model is: a *domain* per study or site; *policies* (single permissions); *modules* that group policies and can be mandatory; versioned *templates* (the form). Consent states are Accepted, Declined, Unknown, Withdrawn, Invalidated, Refused and Expired. Withdrawal can be full or partial, down to one policy. Validity can end on a fixed or computed date. Scans and PDFs attach to a consent. The 2020 paper reports more than 336,000 consents and 2,400 withdrawals since 2014 across large German cohorts. It also says gICS has no authentication of its own. Interfaces are SOAP, plus FHIR (R4, 4.0.1) through the separate TTP-FHIR Gateway. Activity: the GitHub README I opened shows version 2023.1.3 (October 2023); a mirror of the same README shows 2024.3.0 (December 2024); the FHIR gateway package registry shows 2025.1.0 dated 2025-06-19. One caution: a 2024 paper from a large university hospital says the most recent MOSAIC versions were "not distributed as open-source software in a public repository" and that the workflow "Dispatcher" that joins the three tools is not publicly available. Check current source availability before relying on it.

**CTRL** is a participant-facing dynamic consent web app (five-step consent wizard, preference changes, messaging, surveys). The 2021 paper describes Ruby on Rails, PostgreSQL and REDCap integration, shared under a licensing agreement. The Australian BioCommons guide calls it open source with bi-directional APIs. Australian Genomics says the code is in a GitHub repository and free to researchers. I did not find the repository link or a named licence.

**Consent2Share** (Apache-2.0) is a US patient-consent system built from many Java services and a HAPI FHIR server. Main repository last updated May 2020; SMART-on-FHIR parts August 2018. Treat as dormant.

**REDCap** is not open source. Its FAQ says so directly. Licences go only to non-profit organisations that self-host; individuals and for-profit companies cannot get one, and sites may not redistribute the code. It is free to eligible institutions. Its eConsent framework (released to the consortium in March 2018) gives versioned consent forms, a drawn signature, a certification page and automatic PDF archiving. It is a form-and-archive feature, not a consent ledger with scopes.

**Sage Bionetworks.** Synapse is Apache-2.0 and hosted by Sage; the Python client was released 2026-11-04. Bridge, Sage's mobile-study backend, is the closest conceptual match to her design: versioned consent documents, a per-participant sharing scope, a "health code" pseudonym on exported data, and withdrawal [unverified, from memory; current status not checked].

**Mobile consent libraries.** ResearchKit (BSD, iOS) and Stanford's SpeziConsent (MIT, version 0.1.3, January 2026) render a consent document, capture a signature and export a PDF. Neither has a backend. ResearchStack for Android is dormant [unverified].

**Survey tools.** LimeSurvey's "anonymized responses" switch means responses can never be linked to the participant table, even by the admin. So it cannot support a later claim. formr gives each participant an access token that works like a strong password; current version 0.22.0, free hosted instance at Göttingen. Neither has consent versions, scopes or withdrawal as data. OpenClinica Community Edition is LGPL, but participant and ePRO modules belong to the commercial cloud product.

**Dynamic consent platforms.** RUDY is offered through Oxford University Innovation's licensing office, not as open code. The UK Health Research Authority's explainer names RUDY as its one example (2019). A University of Waterloo "Dynamic Consent Standard" project page describes a planned standard and API, last updated April 2021, with no code.

**Newcomers 2023 to 2026.** ClinConNet (arXiv, February 2026) and ConInSe (EU NGI TrustChain) are blockchain or distributed-ledger consent prototypes; ConInSe's code is open to its project community only. Right Consents is a GDPR consent platform, last commit May 2022. c15t (Apache-2.0, about 2,000 stars) is a cookie-banner framework. None targets research participants. A listing of 34 GitHub repositories tagged "pseudonymization" contained no consent-management service.

**Standards-based options, not opened today.** HAPI FHIR can store Consent resources [unverified]. Google Cloud's Healthcare API has a Consent Management API [unverified, status not checked]. Broad's DUOS (named on the DUO page as a DUO user) and CSC's REMS [unverified] manage researcher access requests, which is the "data release" side, not participant consent. GA4GH Passports describe a researcher's identity and access rights as signed "visas" [unverified]; relevant only if she later gives outside researchers controlled access.

## 2. Pseudonymisation and identity separation

**The German "trusted third party" stack** is E-PIX (who is this person, with error-tolerant matching) + gPAS (pseudonyms per domain) + gICS (consent). gPAS generates random pseudonyms and stores the mapping, with de-pseudonymisation and domain-specific alphabets. The Docker Hub image is stuck at 1.9.1 and unmaintained since 2020; newer builds come from the Greifswald site. All three are AGPLv3. Running them is real work: the hospital paper describes a unified REST layer the authors had to build on top. One German university's research-data office offers gPAS and E-PIX only as test systems run by a central trust office, plus an in-house pseudonym tool.

**Mainzelliste** (AGPL-3.0-or-later) is a web service that creates a pseudonym from identifying fields and does record linkage, with a REST interface and audit trail. It is described as actively developed; I could not confirm the current version.

**ACE, the Advanced Confidentiality Engine** (JMIR, 5 November 2025) is the nearest thing to a modern lightweight pseudonym API: Java 21, Spring Boot, PostgreSQL, Keycloak, Docker, REST only. It offers domains, batch calls, and nine generators including salted hashes. It measured about 5,970 transactions per second. It has no consent, no GUI and no record linkage. Its comparison table is useful: it describes gPAS as built for study-specific deployments that do not scale easily to a whole institution, and says Mainzelliste focuses on registration and linkage.

**PEP / PaaS** (Radboud University) wraps polymorphic pseudonymisation in a REST service: each data user gets a different pseudonym for the same person, and the server converts between them without learning the link. paas-api is Apache-2.0, version 0.3.0, February 2025. Early stage.

**Keyed-hash tools.** OpenPseudonymiser is a desktop tool that hashes CSV columns with a salt (version 0.9.7 on a GitHub mirror). The R package deident (JOSS, 2025) builds de-identification pipelines for tabular files. Both show that her HMAC approach is a standard technique, not a novelty.

**Record linkage libraries.** PPRL (R, GPL-3, version 0.3.9, December 2025) covers Bloom-filter and HMAC-based linkage keys. anonlink and clkhash (Apache) last released in May 2023. Splink (MIT, 5.0.0, September 2026) is fast probabilistic linkage but not privacy-preserving. The UK statistics office published an experimental privacy-preserving linkage toolkit that runs in a Google Cloud confidential enclave (April 2024, "not suitable for production use").

**Commercial tokenisation.** Datavant describes patented technology that replaces patient identifiers with encrypted tokens that match across datasets. No pricing is published. A June 2025 trade article names Datavant, Komodo Health and ConcertAI and stresses that participant consent to linkage must be built in from the start.

## 3. De-identification and anonymisation tools

**k-anonymity, l-diversity and t-closeness on tables (survey data):**
- ARX (Apache-2.0, Java, about 670 stars). Supports k-anonymity, l-diversity, t-closeness and differential privacy, with risk analysis. Latest release 3.9.2, dated 21 September (the page did not show the year). The Python wrapper pyARXaaS last released in 2020.
- pyCANON (Apache-2.0, Spanish National Research Council, 1.3.6, August 2026). It only *checks* a dataset and reports k, (α,k), l, entropy l, recursive (c,l), t-closeness, β-likeness and δ-disclosure. Has a command line.
- ANJANA (Apache-2.0, same group, 1.2.3, August 2026). It *applies* the same nine models. An earlier library from the group, python-anonymity, was archived in May 2024.
- sdcMicro (GPL-2, R, 5.7.9). Built for survey microdata: risk estimation, local suppression to reach k-anonymity, recoding, microaggregation, PRAM, noise, and a GUI.
- Amnesia (OpenAIRE, 1.3.4, November 2025). k-anonymity and km-anonymity through a desktop app or browser demo.
- Google Sensitive Data Protection can compute k-anonymity and l-diversity directly on BigQuery tables [unverified]. In plain SQL the basic check is a `GROUP BY` over the quasi-identifiers with `HAVING COUNT(*) < k` [inference].

**Free-text PII scrubbing:**
- Presidio (MIT). Detects and replaces names, emails, phone numbers and similar in text; also images. Runs as Python packages or a Docker REST service. In 2026 the project moved from Microsoft to an independent "Data Privacy Stack" GitHub organisation; latest packages 2.2.366 (2026-10-27). Its own FAQ says there is "no guarantee that Presidio will find all sensitive information" and that its REST endpoints have no built-in authentication. Its structured-data add-on (0.0.10) lists k-anonymity as future work.
- scrubadub (MIT, last release 2023) is a simpler alternative. Google Sensitive Data Protection is the managed alternative [unverified].

**Differential privacy (for published aggregates, not row-level releases):** OpenDP 0.16.0 (MIT, October 2026), SmartNoise SQL 1.0.10 (MIT, April 2026), Tumult Analytics 0.21.0 (Apache-2.0, June 2026, needs Spark), IBM diffprivlib 0.6.6 (MIT, 2025). Anonymeter (1.1.0, July 2026) measures singling-out and linkability risk and was designed for synthetic data.

## 4. Commercial baseline (almost all [unverified]; search budget ran out)

- REDCap: free to non-profit institutions, not available to individuals or companies (verified, see section 1).
- Prolific: a recruitment panel. Researchers see only a Prolific participant ID. The fee is a percentage on top of participant payments, roughly a third for academics when I last saw it [unverified]. Consent is still the researcher's job inside the survey.
- Gorilla: experiment builder with consent-form nodes and anonymous participant IDs; about one pound per participant or a department licence [unverified].
- Qualtrics: enterprise survey platform, usually a university site licence, pricing by quote. Has an "anonymize responses" option. No consent ledger [unverified].
- Castor, Medable, uMotif: clinical-trial eConsent and patient-reported-outcome vendors with quote-based enterprise pricing [unverified].
- MyDataHelps (CareEvolution): participant app platform with eConsent, surveys and device data [unverified; pricing not checked].
- "Citizen": I could not identify this product with confidence [unverified].
- Datavant: no public pricing (verified). Google Sensitive Data Protection: billed per gigabyte inspected or transformed [unverified].
- Pattern [inference]: the commercial baseline splits into (a) recruitment panels that hide identity but do no consent management, (b) survey tools with a consent page and an anonymity switch, and (c) expensive clinical-trial eConsent suites. None sells "consent ledger + pseudonyms as an API" to a small survey team.

## 5. Gap analysis

**Does a lightweight, API-first, cloud-deployable open-source service exist that combines a versioned and scoped consent ledger, pseudonym issuance with identity separation, guest-to-member claim, withdrawal purge and k-anonymous release checks for small survey teams? I did not find one.** Confidence is moderate, not high: the search was cut short and GitHub is large.

What comes closest:
1. **gICS + gPAS + E-PIX.** Functionally the most complete. But it is three Java application-server products plus a gateway and an identity provider, SOAP-first, AGPL, designed for a staffed hospital trust office, with no guest claim and no release checking.
2. **ACE.** The right shape (small REST service, Docker) but pseudonyms only.
3. **Sage Bridge.** Consent versions, sharing scopes, pseudonymous export and withdrawal for mobile studies [unverified]; tied to Sage's AWS hosting.
4. **REDCap.** The default inside universities, with eConsent and identifier tagging, but closed and institution-only.
5. **Google Cloud building blocks** (Sensitive Data Protection, Healthcare Consent Management API) [unverified]. Managed and proprietary.

What would be genuinely new in her module [inference]:
- **The combination in one small service.** Every piece exists somewhere; nobody found here packages them for a FastAPI-sized deployment.
- **Consent as a data-plane filter.** Each research row carries the consent id it was collected under, and scope-filtered warehouse views enforce it. gICS answers "does person Y consent to policy X?"; it does not stamp rows or build views.
- **Guest-to-member claim.** No tool reviewed does this. LimeSurvey's anonymous mode forbids it. formr's access token is the nearest mechanism. The methodological cousin is the self-generated identification code used in anonymous longitudinal psychology studies [unverified].
- **A release gate tied to consent.** Only rows with the "data release" scope enter a release, the k-anonymity check must pass, and the release is tagged with standard data-use terms.
- **Non-clinical survey focus and serverless cloud deployment.** Existing stacks assume hospitals and on-premises servers.

What is not new: HMAC pseudonyms, consent versioning and scopes, partial withdrawal, and k-anonymity itself.

Design weaknesses the existing tools already solved, worth fixing before anyone else adopts the module [inference]:
- **One global pseudonym.** A single `HMAC(pepper, person_id)` links a person across every study and every release. gPAS, ACE and PEP all issue pseudonyms per *domain*. Derive per-study and per-release pseudonyms, for example `HMAC(key, domain + person_id)`, and record the key version so the pepper can be rotated.
- **The test ID is a bearer secret.** Whoever holds it can claim the row. Store only a hash of it, make it single-use, expire it and rate-limit attempts.
- **k-anonymity alone is thin for health-related answers.** Add l-diversity or t-closeness on sensitive columns (pyCANON reports both). Wide questionnaires make k hard to reach; plan generalisation hierarchies.
- **Withdrawal cannot recall a release.** Keep a release register and say this plainly in the consent text. Gate on "withdrawn before release date".
- **Pseudonymised is not anonymous.** While the pepper and identity store exist, research tables are still personal data under GDPR-style rules [unverified; descriptive only].

## 6. What to borrow

**Consent record fields (ISO/IEC TS 27560:2023, as described in the open DPV implementation paper).** Header: schema version, record identifier, creation time. Processing: `privacy_notice`, `language`, `purpose`, `lawful_basis`, `pii_information`, `pii_controllers`, `collection_method`, `processing_method`, `storage_locations`, `retention_period`, `processing_locations`, `jurisdiction`, `recipient_third_parties`, `withdrawal_method`, `privacy_rights`. Parties: `party_name`, `party_role`, `party_contact`, `party_type`. Events: `event_time`, `validity_duration`, `entity_id`, `event_type`, `event_state`. Event states: requested, given, refused, expired, terminated, invalidated, re-affirmed. A *record* is what she keeps; a *receipt* is the copy handed to the participant. Mapping [inference]: each of her scopes becomes one `purpose`; each consent document version becomes a `privacy_notice` with a content hash; give every participant a downloadable receipt. The Kantara Consent Receipt specification is the predecessor of this standard [unverified].

**Consent model (gICS).** Policy, module (with a mandatory flag), versioned template, per-study domain, the seven states above, partial withdrawal per policy, expiry dates, attached signed document.

**Export format (HL7 FHIR Consent).** R5 elements: `status` (draft, active, inactive, not-done, entered-in-error, unknown), `category`, `subject`, `date`, `period`, `grantor`, `controller`, `sourceAttachment`, `policyBasis`, `policyText`, `verification`, `decision`, and nested `provision` with `period`, `purpose`, `action`, `dataPeriod`. R5 is trial-use and research consent is not fully modelled. The German gateway still publishes R4 (4.0.1). Offer an R4 export too [inference]. The Python package fhir.resources (BSD, 8.3.0) provides the model classes.

**Data-use terms for releases (GA4GH DUO, CC BY 4.0).** Verified codes: GRU general research use `DUO:0000042`; HMB health, medical or biomedical research `DUO:0000006`; US user-specific restriction `DUO:0000026`; NCU no commercial use `DUO:0000046`; NPUNCU `DUO:0000018`; NMDS no general methods research `DUO:0000015`. From memory [unverified]: DS disease-specific `DUO:0000007`, ethics approval required `DUO:0000021`, plus publication, collaboration, time-limit and geography modifiers. Mapping [inference]: "test result only" and "linked" or "longitudinal" stay internal purposes; "anonymous research" and "data release" map to GRU or HMB plus modifiers. Open Brain Consent notes that DUO has no term for "no re-identification", so that belongs in the data use agreement. The duo-odrl-dpv repository (CC BY 4.0) shows how to turn DUO terms into machine-checkable rules. If any release may be commercial, such as paid access for other researchers, the consent document needs its own commercial-use purpose; DUO's no-commercial-use and not-for-profit modifiers exist precisely because many participants agree to research but not to sale [inference].

**Withdrawal semantics (descriptive, [unverified]).** GDPR: withdrawal must be as easy as giving consent, does not undo earlier lawful processing, and can trigger erasure. Singapore PDPA: an individual may withdraw on reasonable notice, the organisation must explain the consequences and stop collecting, using and disclosing. Research practice often offers tiers: no further contact, no further collection, no further use and deletion. Record withdrawal as an event; keep the minimal consent evidence; purge research rows by pseudonym; leave a tombstone so a re-import cannot resurrect them. European data-protection guidance on pseudonymisation uses the same "domain" idea and treats keyed hashing as a recognised technique [unverified].

**Libraries to embed.** pyCANON for the release-gate report. ANJANA to generalise and suppress up to the target k. Presidio (analyzer + anonymizer) for free-text answers, with human spot checks. Optional: Google Sensitive Data Protection for BigQuery-native risk jobs; SmartNoise SQL or OpenDP for public dashboards; ARX or sdcMicro offline for complex releases. All four embed candidates are Apache-2.0 or MIT. Keep AGPL (gICS, gPAS, Mainzelliste) and GPL (sdcMicro, PPRL) tools out of the codebase and call them as separate programs if ever needed.

## 7. Recommendation (10 lines)

1. **Build** the M2 core. It is small, specific to her platform, and nothing found replaces it.
2. **Do not invent schemas.** Name ledger fields after ISO/IEC TS 27560, export FHIR Consent, tag releases with DUO.
3. **Embed** pyCANON, ANJANA and Presidio rather than writing anonymity checks or PII detection.
4. **Do not adopt** the Greifswald stack or Mainzelliste: too heavy, AGPL, hospital-shaped. Copy gICS's policy/module/template model.
5. **Integrate later, if needed.** If the PhD university already runs REDCap or a trust office with gICS/gPAS, plan an adapter (FHIR Consent out, their pseudonyms in), not a replacement.
6. **Is it a real gap?** For independent researchers and small psychology or social-science teams, yes, on this evidence [inference]. For medical faculties, less so: they already have REDCap and trust offices.
7. **Fix first:** per-domain pseudonyms with key versions, test ID handled as a secret, l-diversity next to k-anonymity, a release register.
8. **Open source before hosted.** A hosted API makes her the processor of other people's participant identities, with contracts, security review and liability [inference]. Start as a self-hostable Apache-2.0 package with one-command deployment.
9. **What a university will ask for** [inference]: self-hosting, an audit log, a threat model, a data-protection impact assessment template, standards alignment, and evidence of ethics approval for any data collected with it.
10. **Test demand cheaply:** show the README and API sketch to three to five labs and one university research-data office before building anything hosted.

## Sources (opened today)

- gICS: https://github.com/mosaic-hgw/gICS ; mirror https://github.forks.workers.dev/mosaic-hgw/gICS ; paper https://pmc.ncbi.nlm.nih.gov/articles/PMC7391490
- gPAS: https://hub.docker.com/r/tmfev/gpas ; E-PIX paper: https://link.springer.com/content/pdf/10.1186/s12967-020-02257-4.pdf
- TTP-FHIR Gateway: https://github.com/mosaic-hgw/ttp-fhir-ig ; https://packages2.fhir.org/packages/ths-greifswald.ttp-fhir-gw
- Hospital trust-office paper (2024): https://medinform.jmir.org/2024//e53075 ; university service page: https://uol.de/en/school6/fdm/pseudonymisation
- Mainzelliste: https://www.unimedizin-mainz.de/imbei/en/informatik/ag-verbundforschung/mainzelliste-as-an-open-source-service.html ; https://helmholtz.software/software/mainzelliste
- ACE (2025): https://www.jmir.org/2025/1/e71822/XML
- PEP / PaaS: https://opensource.cs.ru.nl/projects/paas ; https://lib.rs/crates/paas-api
- GitHub topic listing: https://repos.ecosyste.ms/topics/pseudonymization
- OpenPseudonymiser: https://www.github.com/drcjar/OpenPseudonymiser ; deident: https://eprints.staffs.ac.uk/8656/1/10.21105.joss.07157.pdf
- CTRL: https://pmc.ncbi.nlm.nih.gov/articles/PMC8115139 ; https://australianbiocommons.github.io/human-omics-data-sharing-field-guide/ctrl ; https://www.australiangenomics.org.au/?p=3674
- Consent2Share: https://github.com/bhits
- REDCap: https://projectredcap.org/about/faq/ ; eConsent paper: https://cambridge.org/core/services/aop-cambridge-core/content/view/S2059866120000308
- Sage: https://infrafinder.investinopen.org/solutions/synapse ; https://github.imc.re/orgs/Sage-Bionetworks/repositories?type=all
- ResearchKit: https://github.com/ResearchKit/ResearchKit ; SpeziConsent: https://swiftpackageregistry.com/StanfordSpezi/SpeziConsent
- OpenClinica: https://www.openclinica.com/get-free-community-edition-software/
- formr: https://formr.org/about ; https://github.com/rubenarslan/formr/ ; LimeSurvey: https://www.limesurvey.org/manual/Participant_settings
- Dynamic consent: https://innovation.ox.ac.uk/licence-details/rare-uk-diseases-study-platform ; https://hra.nhs.uk/about-us/news-updates/what-dynamic-consent ; https://uwaterloo.ca/ubiquitous-health-technology-lab/current-projects/dynamic-consent-interoperability-resources
- Newcomers: https://arxiv.org/abs/2602.02610 ; https://trustchain.ngi.eu/is-cis/ ; https://sourceforge.net/p/right-consents/code ; https://openalternative.co/tags/consent-management
- Standards: https://www.hl7.org/fhir/consent.html ; https://arxiv.org/pdf/2405.04528 ; https://github.com/EBISPOT/DUO ; https://open-brain-consent.readthedocs.io/en/latest/duo.html ; https://www.github.com/besteves4/duo-odrl-dpv
- ARX: https://www.github.com/arx-deidentifier/arx/releases ; https://science.ecosyste.ms/projects/15895 ; https://smo-wiki.leibniz-hbi.de/Data-Anonymization-Tools
- pyCANON and ANJANA: https://pycanon.readthedocs.io/en/latest/ ; https://anjana.readthedocs.io/en/latest/ ; https://www.github.com/IFCA-Advanced-Computing/python-anonymity
- sdcMicro: https://rdrr.io/cran/sdcMicro/ ; Amnesia: https://www.openaire.eu/amnesia-1-3-4-new-release-enhances-privacy-protections-and-user-experience
- Presidio: https://raw.githubusercontent.com/microsoft/presidio/main/README.MD ; https://microsoft.github.io/presidio/structured ; https://www.github.com/microsoft/presidio/blob/main/docs/faq.md ; https://www.everydev.ai/developers/data-privacy-stack
- Record linkage: https://cran.r-project.org/web/packages/PPRL/refman/PPRL.html ; https://datasciencecampus.ons.gov.uk/developing-a-privacy-preserving-record-linkage-toolkit/
- Tokenisation: https://www.datavant.com/?p=3084 ; https://www.appliedclinicaltrialsonline.com/view/tokenization-unsexy-plumbing-clinical-research
- Package versions, dates and licences (Presidio, pyCANON, ANJANA, OpenDP, SmartNoise SQL, Tumult Analytics, diffprivlib, anonlink, clkhash, Splink, scrubadub, anonymeter, fhir.resources, synapseclient, pyARXaaS): PyPI registry records at `https://pypi.org/pypi/<package>/json`, read 2026-11-16.

Opened but empty or unusable: Kantara wiki pages (not found), OpenAIRE catalogue page for Amnesia (JavaScript only), a DKFZ-hosted PDF of a pseudonymisation benchmark paper (bot check), one Datavant blog post.

Blocked by an unanswered permission prompt, so not read: https://github.com/mosaic-hgw/gPAS ; https://github.com/mosaic-hgw/E-PIX ; https://github.com/bhits-dev/consent2share ; https://new.mainzelliste.de/ ; https://w3c-cg.github.io/dpv/guides/consent-27560 ; https://github.com/datasciencecampus/pprl_toolkit ; https://github.com/miracum/vfps
