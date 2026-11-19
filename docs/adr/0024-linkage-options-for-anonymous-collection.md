# ADR-0024: Anonymous collection: participant-held code for linkage and withdrawal, self-generated code as recovery, blind participation token for one response per member

**Status:** Proposed
**Date:** 2026-11-19
**Deciders:** Owner (Elena Okhonko)

## Context

v4 named two collection modes and warned that anonymous mode needs more than leaving out a key. Longitudinal questions and retest reliability need a way to link a person's responses across waves; withdrawal needs a way to find a response; member-only surveys need one response per member. Self-generated codes are the established method for anonymous panels, with published match rates from about half of cases across three waves with strict matching to above 95% with tolerant matching of longer codes, and errors that are mostly missed links.

## Decision

Linkage is a field of the ethics policy with four values: `none`, `participant_code`, `self_generated_code`, `research_id`. For anonymous studies the default is a random code shown once and kept by the participant (on the device and written down), used to link waves and to withdraw inside a stated window. A short self-generated code is offered only as recovery when the random code is lost: its elements are stored as keyed hashes, matched element by element with one element allowed to differ, and never released. Each link is recorded as `exact`, `recovered` or `unlinked`. One response per member is enforced by a single-use participation token issued by blind signature. Two things need an independent check, in this order: the anonymous path itself (its own address, no cookies, no request logs, no network address, coarse times, batched release), and then the token. Until the path has passed, no study rests on anonymity at all. Until the token has passed, member-only anonymous surveys are not offered: an anonymous study uses an open link without duplicate control and says so in its limitations.

## Options Considered

| Option | Complexity | Cost | Scalability | Fit for a solo owner | For | Against |
| --- | --- | --- | --- | --- | --- | --- |
| A. Participant-held random code, self-generated code as recovery, blind token (chosen) | Medium | None | Large | Good | No personal fact in the main path; recovery limits attrition; cryptographic unlinkability | Lost codes; the blind token needs an outside check before it is trusted |
| B. Self-generated code as the only link | Low | None | Large | Good | Well studied; nothing to keep | Elements are indirect identifiers; high missed-link rates without tolerant matching |
| C. Pseudonymous `research_id` for everything | Low | None | Large | Fair | Exact linkage, withdrawal and recontact | Identifiable to the platform, so every study needs outside review |
| D. Trust the operator: participant table and response table kept apart | Low | None | Large | Fair | What common survey tools do | Unlinkability rests on a promise and on logs nobody reads |

## Trade-off Analysis

A costs the most to build and gives the strongest claim. C remains the right choice for a cohort that wants recontact and verified diagnosis; the two modes coexist and the study's archetype decides.

## Consequences

- Easier: retest and wave-to-wave analysis without identities.
- Harder: analysis must model unlinked cases as missing, not as new people.
- Released datasets never contain codes or their elements.
- Revisit when: the blind token has passed an independent check, and after the first two-wave study reports its link rates.

## Action Items

1. [ ] Specify the token and the code flow in the Stage 3 plan
2. [ ] Commission an independent check of the anonymous path before any route rests on it
3. [ ] Record link quality in the response schema
