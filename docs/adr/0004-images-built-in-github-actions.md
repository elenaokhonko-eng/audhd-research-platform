# 0004 Container images are built in GitHub Actions, not Cloud Build

Date: 2026-11-15 · Status: accepted

Context: the earlier plan said Cloud Build owns images. Building in GitHub Actions needs no extra Google service account permissions and is free for a public repository.
Decision: GitHub Actions builds, tags with the commit SHA, pushes to Artifact Registry and deploys, authenticating through Workload Identity Federation. Prod deploys only from a `v*` tag and only through the `production` environment, which requires the owner's approval.
Consequences: one CI system to read. Cloud Build stays available for jobs that must run inside Google Cloud.
