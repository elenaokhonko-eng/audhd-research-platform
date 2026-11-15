# 0005 Public Cloud Run services use invoker_iam_disabled, not allUsers

Date: 2026-11-15 · Status: accepted

Context: the project sits in a Google Workspace organisation whose secure-by-default policy `iam.allowedPolicyMemberDomains` (domain restricted sharing) refuses IAM bindings to `allUsers`. Terraform's first apply failed on exactly that binding for web-dev and web-prod.
Decision: public services set `invoker_iam_disabled = true` and carry no `allUsers` binding. The organisation policy stays as it is for everything else.
Consequences: the website is public; nothing else in the project can be made public by accident through IAM. If an organisation later also enforces `run.managed.requireInvokerIam`, a project-level exception for that one constraint is needed.
