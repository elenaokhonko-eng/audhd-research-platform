# 0003 DNS on Cloudflare; Cloud Run domain mapping for the MVP

Date: 2026-11-15 · Status: accepted, revisit when traffic grows

Context: the registrar placed the zone on Cloudflare; the owner has admin rights. Cloud Run domain mappings are free but in preview and documented as having latency issues; a global external Application Load Balancer is the production route (~US$18/month).
Decision: keep DNS on Cloudflare, managed by Terraform with DNS-only (grey cloud) records; use Cloud Run domain mappings for apex, www and dev.
Consequences: zero extra cost for the subscriber preview. Switching to the load balancer later changes only domain.tf and the DNS records; nothing in the site changes.
