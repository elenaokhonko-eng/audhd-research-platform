# Content model: public code, private research

This repository is public. Research content is not. The two live side by side on disk and never mix in git.

```text
audhd/                          one parent folder on the development machine
├─ audhd.code-workspace         open this in VS Code: shows both folders
├─ audhd-research-platform/     THIS repo, public on GitHub
└─ audhd-research-private/      research content, no git remote, never pushed
```

## What goes where

| Lives in this repo (public) | Lives in `audhd-research-private` (never pushed) |
| --- | --- |
| Application code, infrastructure, CI, tests | Article drafts and Substack-ready posts |
| Architecture docs, ADRs, runbooks | Research reports, evidence reviews, references |
| Agent definitions and prompts that hold no research findings | Study designs, protocols, questionnaires |
| Schemas and folder conventions (this file) | Phenotype canon, card decks, artwork |
| Placeholder or synthetic sample data | Case files, consent forms, correspondence |
| | Build scripts that embed article text |

When in doubt, it is private. Moving something from private to public later is easy; taking it back off a public repo is not.

## How code finds the content

Code reads the private folder through one setting, never a hard-coded path:

```bash
# .env (git-ignored)
AUDHD_CONTENT_DIR=../audhd-research-private
```

Agents and scripts must treat a missing `AUDHD_CONTENT_DIR` as "no content available" and stop, never fall back to a folder inside the repo.

## Private folder layout

```text
audhd-research-private/
├─ series/NN-slug/              one folder per article series
│  ├─ articles/NN-slug/         article.md, substack.md, hero.png, research-graph.png
│  ├─ assets/ reports/ research/ versions/ publishing/
│  └─ README.md
├─ canon/ research/ references/ study-design/ shared/
├─ standalone/ planning/ tools/ unsorted/
├─ private/                     case files and correspondence: most restricted
└─ docs/                        naming convention, manifests
```

Naming: lowercase kebab-case; articles as `NN-slug/`; extra versions in `versions/`.

## Safeguards in this repo

1. The private folder sits outside the repo, so `git add -A` cannot see it.
2. `.gitignore` blocks the private folder names and document types as a backstop.
3. `ops/scripts/check-private-content.sh` rejects private folders, case-file names, office documents, archives and files over 5 MB. It runs:
   - before each local commit, once you enable the hook: `git config core.hooksPath .githooks`
   - on every pull request and push to `main` (`.github/workflows/private-content-guard.yml`).
4. Back up `audhd-research-private` separately (for example to a private cloud bucket or a private repo). This repo is not a backup for it.
