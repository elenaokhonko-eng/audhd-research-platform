# Security and responsible data handling

## Public repository boundary

This repository contains application code and synthetic configuration examples only.

Never commit:

- patient or participant records, identifiers, dates, case notes, or re-identification keys;
- clinical exports, research datasets, paper files whose licenses prohibit redistribution, or generated embeddings from restricted data;
- `.env` files, API keys, database credentials, access tokens, private URLs, or cloud service-account files;
- production logs, LangSmith trace exports, approval snapshots, generated reports, or artifact-store contents containing sensitive material.

Clinical and restricted research data must live in approved encrypted data services outside Git. Use synthetic fixtures for tests and demonstrations.

## Vulnerability reporting

Do not open a public issue containing a vulnerability, credential, or sensitive record. Use GitHub private vulnerability reporting once it is enabled for the repository.

## Clinical safety

The software is a research-support and publishing platform. It is not a diagnostic device and must not be used to make autonomous clinical decisions. Any deployment processing clinical information requires independent privacy, security, ethics, and regulatory review.
