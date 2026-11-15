# 0002 One Google Cloud project for Stage 0, dev and prod as separate services

Date: 2026-11-15 · Status: accepted, revisit before Stage 1

Context: Stage 0 serves a public, data-free website. Separate projects per environment double billing setup, IAM and Terraform state.
Decision: one project `audhd-neurobiology-prod`; `web-dev` and `web-prod` are separate Cloud Run services; resources are named per environment.
Consequences: cheap and simple now. Before Stage 1 stores personal data, create `audhd-neurobiology-dev` so test data never shares a project with real participant data; the Terraform module boundary already allows it.
