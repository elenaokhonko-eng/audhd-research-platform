# AutoRA for the research loop kit: reuse, port, or ignore

Date: 2026-11-16. Method: 17 AutoResearch repos and 8 alternative repos were cloned read-only (depth of reading is stated under Sources); PyPI metadata was queried; `autora-core` 5.0.3 was installed and exercised in a scratch virtualenv. Tags: [inference] = my reasoning from code, [unverified] = could not be checked here.

## Summary table

| Component of her loop | AutoRA piece | Verdict | What to take |
|---|---|---|---|
| (a) Loop state and cycle orchestration | `State`, `Delta`, `on_state`, `StandardState` in `autora-core/src/autora/state.py`; CLI in `autora/workflow/__main__.py` | Port the pattern only | The "step(state) returns a delta, state = fold of deltas" contract, per-field merge policy (extend / append / replace), and the "one step per process, load state, run, dump state" CLI idea. Not the in-process for-loop or pickle files. |
| (b) Experimentalist (what to ask next) | `autora.experimentalist.grid/random` in core; novelty, uncertainty, model-disagreement, falsification packages | Port the pattern only; shipped samplers not applicable | The role name and signature (state in, `conditions`/design out). Optionally the idea of scoring a pool of candidates. The samplers pick numeric values of independent variables, not survey items. |
| (c) Experiment runner (field survey, return responses) | `firebase_prolific/__init__.py`, `experimentation_manager/firebase/__init__.py`, `recruitment_manager/prolific/__init__.py` | Port the pattern only; borrow Prolific code only if she later buys panel respondents | The slot status machine (`available` / `unavailable` / `finished`, timeout frees a slot). Split it into non-blocking `publish` and `collect`. |
| (d) Theorist (pattern detection) | `estimator_on_state`; BMS, BSR, DARTS packages | Adopt the interface (scikit-learn `fit`/`predict`), not the theorists | Wrap her analysis job behind an estimator-like object. BMS and DARTS are a poor fit for questionnaire data. |
| (e) Reporting and documentation | `autodoc` (`autora-doc` 0.0.5) | Not applicable | Nothing. It documents AutoRA code with Llama-2; it does not write findings. |
| Test harness (not asked, but the best reuse) | `autora-synthetic` ground-truth runners plus the plain for-loop | Port the pattern; optional dev-only dependency | A synthetic respondent generator with a planted pattern, so the whole loop can be dry-run in CI. |

Short answer: there is a GitHub repo and it is MIT, but the reusable code is about 150 lines of state logic. The design should be ported, not installed as a production dependency.

## 1. Repos, licence, health

All repos live under `https://github.com/AutoResearch/`. Licence in every cloned AutoRA repo is MIT ("Copyright (c) 2023 Autonomous Empirical Research Initiative" in `autora/LICENSE`). Docs: `https://autoresearch.github.io/autora/` (the landing page says "in active development" and lists no LLM components). Citation: JOSS paper DOI 10.21105/joss.06839 (from `README.md` and `CITATION.cff`).

| Repo (PyPI name is the same unless noted) | Latest PyPI release | Last commit on default branch | Notes from code |
|---|---|---|---|
| `autora` | 4.2.0, 2024-12-04 | 2025-08-12 | Umbrella only: `packages = []`; depends on `autora-core` and `autora-synthetic`; everything else is an extra. |
| `autora-core` | 5.0.3, 2024-10-13 | 2025-04-18 | 3,186 lines of Python; `state.py` is 1,735 lines, mostly doctests. Deps: `numpy>=1,<2`, matplotlib, pandas, scikit-learn, `typer[all]`. |
| `autora-experiment-runner-firebase-prolific` | 1.0.1, 2024-06-28 | 2026-04-26 | 307 lines. HEAD is ahead of PyPI. |
| `autora-experiment-runner-experimentation-manager-firebase` | 1.1.5, 2025-08-12 | 2026-04-26 | 477 lines. Deps: firebase-admin, numpy. |
| `autora-experiment-runner-recruitment-manager-prolific` | 1.0.1, 2024-06-28 | 2026-04-26 | 835 lines. Imports `requests` but declares only `autora-core` as a dependency. |
| `autora-theorist-bms` | 1.0.6, 2023-08-23 | 2023-12-01 | Deps: scikit-learn, tqdm, sympy. |
| `autora-theorist-darts` | 1.1.0, 2024-07-28 | 2024-07-30 | Deps: torch, graphviz, matplotlib. |
| `autora-theorist-bsr` | 1.0.0, 2023-05-31 | not cloned | Listed in docs; code not read. |
| `autora-synthetic` | 2.2.0, 2024-10-13 | 2024-07-26 | Ground-truth models (Weber-Fechner, prospect theory, Q-learning, etc.). |
| `autora-workflow` | 0.6.0, 2023-12-01 | 2023-12-01 | README says deprecated and merged into `autora-core`. |
| `autora-experimentalist-model-disagreement` | 2.2.0, 2024-10-11 | 2024-10-13 | Novelty and falsification repos last changed 2024-07-26. |
| `autodoc` (PyPI `autora-doc`) | 0.0.5, 2024-02-08 | 2025-03-20 | Pins `torch==2.0.1`, `transformers==4.37.2`. |
| `SweetBean` (PyPI `sweetbean`) | 1.3.17, 2025-10-21 | 2026-05-11 | MIT. Python to jsPsych generator; has `TextSurvey`, `MultiChoiceSurvey`, `LikertSurvey` in `src/sweetbean/stimulus/Survey.py`. |
| `autora-user-cookiecutter` | not on PyPI | 2025-09-23 | Project template: `researcher_hub` (Python workflow) plus a Firebase web app. |

Maintainers listed in `autora/pyproject.toml`: author Sebastian Musslick; maintainers Ben Andrew, George Dang, John Gerrard Holland, Younes Strittmatter. Commit activity (from `git log` after deepening the clones): `autora` had 31 commits between 2024-11-16 and 2025-11-16 (Musslick 20, Strittmatter 9) and none since; `autora-core` had 1 commit in the last two years; the three runner repos had 10, 3 and 14 commits since 2025-11-16, all by Younes Strittmatter. So the core is dormant and stable, and the Firebase/Prolific runner is the only part with 2026 work, by one person. [inference]

Python support: `autora-core` declares `requires-python >=3.8,<4` and classifiers up to 3.12. The `numpy<2` pin matters: PyPI lists numpy 1.26.4 (2024-02-05) wheels only for CPython 3.9 to 3.12. On Python 3.13.18 here, `pip install autora-core` did succeed and resolved numpy 1.26.4, pandas 3.0.6, scikit-learn 1.9.1 (34 packages, 328 MB virtualenv); numpy was presumably built from source [inference]. Any service that imports `autora-core` is held on numpy 1.x.

Release mismatch: `firebase_prolific` at HEAD imports `get_observations_with_meta`, which was added to the Firebase manager in the commit after tag v1.1.5. The 2026 runner code therefore cannot be installed from PyPI; it would have to be installed from git.

Not verified: GitHub stars, open issues and the full list of organisation repos (the GitHub REST API is not available in this session). Two guessed repo names for LLM-based components (`autora-theorist-llm`, `autora-experimentalist-llm`) do not exist as public repos, and the docs and code I read contain no literature or LLM step, which matches the earlier review.

## 2. How AutoRA works (from the code)

State. `State` (`autora-core/src/autora/state.py`, line 49) is a frozen dataclass. Each field carries metadata: `{"delta": "extend" | "append" | "replace"}`, an optional `"converter"` and optional `"aliases"`. `State.__add__` (line 216) takes a `Delta` or mapping and returns a new State; unknown keys produce a warning, not an error. `Delta` (line 522) is a plain `UserDict`. Extension is type-dispatched in `_extend` (lines 545 to 650): lists concatenate, DataFrames use `pd.concat(..., ignore_index=True)`, dicts merge.

Wrappers. `on_state` (line 1159) composes three helpers: `outputs_to_delta` (name the outputs), `inputs_from_state` (line 677) and `delta_to_state` (line 995). Inputs are injected by parameter name, in the style of pytest fixtures: a function `def f(conditions, variables)` receives `state.conditions` and `state.variables`; a parameter called `state` receives the whole object; other keyword arguments pass through. Signature: `on_state(function=None, input_mapping={}, output=None)`.

StandardState (line 1264) has four fields: `variables` (replace), `conditions` (replace, DataFrame), `experiment_data` (extend, DataFrame) and `models` (extend, a list of fitted scikit-learn-style estimators, alias `model`). Properties `X` and `y` slice `experiment_data` by the independent and dependent variable names.

Variables. `Variable` (`autora-core/src/autora/variable/__init__.py`) has `name`, `value_range`, `allowed_values`, `units`, `type`, `variable_label`, `rescale`, `is_covariate`. `ValueType` offers boolean, integer, real, sigmoid, probability, probability_sample, probability_distribution and class. `VariableCollection` holds `independent_variables`, `dependent_variables`, `covariates`.

Components. An experimentalist is any function that returns `conditions` (core ships `grid.pool`, a Cartesian product of `allowed_values`, and `random.pool` / `random.sample`). An experiment runner maps conditions to a DataFrame of conditions plus observations (`experiment_runner_on_state`, line 1618). A theorist is a scikit-learn estimator; `estimator_on_state` (line 1575) fits `experiment_data[ivs]` against `experiment_data[dvs]` and appends the estimator to `models`.

Running a cycle. There is no scheduler. The README, the tutorials and `docs/examples/closed-loop-basic/workflow.md` all use a plain Python loop: `for _ in range(n): state = runner(state); state = theorist(state); state = experimentalist(state)`. Everything is held in memory. For long-running steps, `docs/cli/index.md` describes `python -m autora.workflow module.function --in-path A --out-path B`, which loads a pickled (or dill, or YAML) State, runs one function and dumps the State; `docs/cli/cylc-pip/flow.cylc` chains those calls with the Cylc workflow manager. That CLI is 81 lines (`autora-core/src/autora/workflow/__main__.py`).

## 3. What the Firebase + Prolific runner actually does

Firebase manager (`experimentation_manager/firebase/__init__.py`). `send_conditions` writes one Firestore document per condition row under `autora/autora_in/conditions/{i}`, an empty placeholder under `autora/autora_out/observations/{i}`, and a slot map in `autora/autora_meta` with `start_time` and `finished` per slot. By default it deletes the previous conditions and observations first (`is_append=False`). The web experiment claims a slot and writes its observation back (client code lives in the React template, which I did not read). `check_firebase_status` returns `available`, `unavailable` or `finished`, and frees slots whose participant timed out or returned the study. `get_observations` reads the observations collection.

Prolific manager (`recruitment_manager/prolific/__init__.py`). Plain `requests` calls to `https://api.prolific.com/api/v1/`. `setup_study(name, description, external_study_url, estimated_completion_time, prolific_token, ..., reward=0, total_available_places=1, eligibility_requirements=[...], device_compatibility=["desktop"], project_id=None)` creates a draft; `publish_study`, `pause_study`, `start_study`, `stop_study` change its status; `check_prolific_status` returns places taken and finished submissions; `approve_all`, `approve_all_no_code` and `request_return_all` settle submissions.

Combined runner (`firebase_prolific/__init__.py`). `firebase_prolific_runner(**kwargs)` returns a function of conditions. It uploads the conditions, creates a Prolific draft with `total_available_places=len(conditions)` (one participant per condition row), then blocks in `while True: ... time.sleep(sleep_time)`. Each pass it checks Firebase, frees returned or timed-out slots, publishes or resumes the Prolific study when slots are free, pauses it when none are, approves submissions that arrived without a completion code every fifth pass (or asks for their return if `approve_no_code=False`), and returns when Firebase reports `finished` or Prolific reports `COMPLETED`. At HEAD the return value is a list of `{slot_key, prolific_pid, obs}` envelopes. `firebase_runner` is the same without recruitment.

## 4. Fit assessment for her loop

(a) Loop state and orchestration: port the pattern only. The valuable idea is small: every step is a function of the state that returns a delta, and each field declares how deltas merge. That maps cleanly onto her design, where each Pub/Sub event (`pattern.detected`, `gap.identified`, `finding.candidate`) is in effect a delta on a loop-cycle record. AutoRA's orchestration does not map: it is an in-process loop with pickle files, while her loop waits days or weeks for a pull-request approval and for responses, crosses Python and TypeScript, and has BigQuery as the system of record. `state.py` also imports numpy, pandas and scikit-learn at module load, which is heavy for an orchestrator. Reimplement the merge logic (about 100 to 150 lines without doctests) as a pydantic model, since her services already use pydantic.

(b) Experimentalist: port the pattern only. AutoRA experimentalists rank or sample rows from a numeric pool of conditions; model disagreement, for example, calls `predict` on two models over the pool and picks the rows where predictions differ most (`model_disagreement/__init__.py`, `compute_disagreement`). Her step chooses items and instruments from YAML templates in response to a literature gap, drafts wording, and stops at a human gate. None of the samplers do that. One idea carries over: treat the template library as the pool (one row per candidate item or module, with features such as construct, burden in minutes, gap score, sensitivity tier) and score it before the agent drafts. [inference]

(c) Experiment runner: port the pattern only. Reasons not to adopt: it assumes Firestore as transport, one participant per condition row, a blocking poll loop, paid external recruitment and a service-account dict passed in code; it has no notion of consent scope, withdrawal or membership. What is worth copying is the three-state status check and the timeout rule, expressed against her own tables: an instrument version is `open`, `awaiting_approval`, `fielding` or `closed`, with a target n and a deadline. If she later wants a paid panel, the Prolific manager is the piece to borrow: `setup_study`, `publish_study`, `pause_study`, `check_prolific_status`, `get_submissions_incompleted`, `approve_all`.

(d) Theorist: adopt the interface, not the theorists. `BMSRegressor.fit(X, y, num_param=1, root=None, custom_ops=None, random_state=None)` runs `check_X_y`, then a parallel-tempering MCMC over expression trees (`bms/parallel.py`, `bms/mcmc.py`) built from operators such as sin, exp, log and powers, scored by BIC computed from the sum of squared errors. It searches for one closed-form equation for one continuous dependent variable. `DARTSRegressor` is a neural architecture search that needs torch and supports output types real, sigmoid and probability variants. Questionnaire data is ordinal, high-dimensional, collinear and observational, and the questions are about latent structure and subgroups: reliability, factor structure or IRT, measurement invariance, latent classes or clusters, and regression with confounders. Symbolic regression answers none of those and will overfit Likert items treated as real numbers. [inference from the code and the method] A narrow use remains: exploring the shape of a relation between a few continuous composite scores (for example a symptom score against age or cycle phase), as a supplement. I confirmed the obvious limit: `estimator_on_state(LinearRegression())` on a State with a string-valued column raises `ValueError: could not convert string to float`.

(e) Reporting: not applicable. The README mentions "documentation for open science", but the only code is `autodoc`, which prompts Llama-2 to describe AutoRA code (`src/autora/doc/runtime/prompts.py`). There is no findings report, preregistration, provenance or audit trail. `BMSRegressor.present_results()` prints an equation and a plot.

## 5. Sketch: her kit as AutoRA-compatible components

SKETCH ONLY. Python-like pseudocode, not runnable. Helper names on her side (`rank_gaps`, `open_pull_request`, `bq_count_responses`, and so on) are invented placeholders. The custom `State` with dict, list and string fields is real: a smaller version of it ran two cycles and survived a pickle round trip on `autora-core` 5.0.3.

```python
from dataclasses import dataclass, field
from autora.state import State, Delta, on_state

@dataclass(frozen=True)
class SurveyLoopState(State):
    protocol:  dict = field(default=None, metadata={"delta": "replace"})   # study protocol, consent scopes, burden cap
    gaps:      list = field(default_factory=list, metadata={"delta": "extend"})    # gap.identified payloads
    design:    dict = field(default=None, metadata={"delta": "replace"})   # instrument draft + PR url + target n
    fielding:  dict = field(default=None, metadata={"delta": "replace"})   # instrument_version, status, n, deadline
    data_ref:  dict = field(default=None, metadata={"delta": "replace"})   # BigQuery table + snapshot time + scope, NOT rows
    patterns:  list = field(default_factory=list, metadata={"delta": "extend"})    # pattern.detected payloads
    findings:  list = field(default_factory=list, metadata={"delta": "extend"})    # finding.candidate payloads

class NotReady(Exception): ...          # AutoRA has no such concept; her loop needs it

@on_state()
def literature_gap_experimentalist(gaps, protocol, patterns):
    gap = rank_gaps(gaps, patterns)[0]
    items = select_items(template_library(), gap, max_minutes=protocol["max_burden_min"])
    pr_url = open_pull_request(render_instrument_yaml(items, protocol))    # human gate
    return Delta(design={"gap_id": gap["id"], "pr_url": pr_url, "target_n": protocol["target_n"]})

@on_state()
def survey_experiment_runner(design, fielding):
    if fielding is None:                                   # phase 1: publish, return at once
        if not pr_merged(design["pr_url"]):
            raise NotReady("awaiting owner approval")
        version = publish_instrument(design["pr_url"])
        return Delta(fielding={"instrument_version": version, "status": "fielding"})
    n = bq_count_responses(fielding["instrument_version"], consent_scope="research")
    if n < design["target_n"] and not past_deadline(fielding):             # phase 2: collect, called again later
        raise NotReady("still fielding")
    return Delta(fielding={**fielding, "status": "closed", "n": n},
                 data_ref=bq_snapshot_ref(fielding["instrument_version"]))

@on_state()
def pattern_theorist(data_ref, fielding):
    job = run_analysis_job(data_ref)                       # her psychometrics + clustering job in BigQuery/Python
    return Delta(patterns=job.patterns)                    # each one is also published as pattern.detected

STEP_FOR_EVENT = {"gap.identified": literature_gap_experimentalist, "survey.approved": survey_experiment_runner,
                  "survey.poll": survey_experiment_runner, "responses.ready": pattern_theorist}

def handle(event):                      # one step per Pub/Sub delivery, replacing AutoRA's in-process for-loop
    state = load_state(event["loop_id"])                   # a row in her store, not a pickle
    try:
        new_state = STEP_FOR_EVENT[event["type"]](state + Delta(**event.get("delta", {})))
    except NotReady:
        return                                             # ack; a scheduled survey.poll event retries later
    save_state(event["loop_id"], new_state)
    publish_next_event(event, new_state)
```

What does not fit AutoRA's assumptions:

1. Controlled conditions. AutoRA is built around manipulated independent variables with numeric ranges and measured dependent variables. A member survey is observational; the only "condition" is the instrument version. `StandardState.X`, `.y` and `estimator_on_state` are therefore of little use, which is why the sketch defines its own State.
2. One row, one participant. The Firebase runner sets recruitment places to the number of condition rows. Her fielding is one instrument to many members with a target n and a deadline.
3. Long waits and human approval. Every AutoRA runner blocks until data arrives. There is no "pending" result, so the sketch has to add `NotReady` and a two-phase runner. AutoRA's own answer is the CLI with pickled state between jobs.
4. Data protection. The State accumulates raw rows in `experiment_data` and is persisted by pickle, dill or YAML. There is no consent scope, withdrawal, retention or minimisation. Her state should hold references to BigQuery snapshots, as in `data_ref` above.
5. No event bus and no TypeScript. Components are Python callables. Her Genkit agents can only share a JSON event and delta contract, not `on_state`.
6. No literature step, and no vocabulary for findings, gaps, evidence or who approved what.
7. Models are a list of fitted estimators. Her outputs are clusters, factor structures and effect sizes with uncertainty, which need their own schema.
8. Dependency constraints: the numpy 1.x pin and a core that has not been released since October 2024.

## 6. Alternatives and complements

catsim (`https://github.com/douglasrizzo/catsim`, BSD-3-Clause, PyPI 0.21.0 of 2026-04-08, last commit 2026-10-28). A Python computerized adaptive testing engine with separate initialisation, item selection, ability estimation and stopping modules; dependencies are scipy, numexpr, matplotlib, tqdm, numpy. It covers what AutoRA lacks inside a single survey session: choosing the next item for one respondent. It works with unidimensional logistic IRT models and needs a calibrated item bank; I found no graded-response (Likert) model in its Python source [inference from a text search], so it suits yes/no screeners more than rating scales.

mirtCAT (`https://github.com/philchalmers/mirtCAT`, GPL (>= 3), version 1.14.3, last commit 2025-06-16). An R package on top of `mirt` and Shiny that supports unidimensional and multidimensional adaptive tests and plain questionnaires, and so handles polytomous items. It is the stronger psychometric engine, but it is R and GPL: run it as a separate calibration or simulation job, not inside the FastAPI services. Concerto (`https://github.com/campsych/concerto-platform`, Apache-2.0, last commit 2026-10-23) is a full PHP plus R adaptive testing platform (its Dockerfile installs `catR`); it would replace her survey front end, so it is a reference design at most.

HypoGeniC (`https://github.com/ChicagoHAI/hypothesis-generation`, MIT, PyPI `hypogenic` 0.3.5 of 2025-07-16, Python >= 3.10). LLM-driven hypothesis generation from labelled datasets, with "HypoRefine" and union methods that combine hypotheses from literature PDFs with data-driven ones. This is the closest open-source match to her `pattern.detected` to `finding.candidate` / `gap.identified` step. It is framed around classification tasks with a config file per task, so expect to port the prompt-and-update loop, not to install it as is. [inference]

PaperQA2 (`https://github.com/Future-House/paper-qa`, Apache-2.0, PyPI `paper-qa` 2026.8.12, Python >= 3.11, last commit 2026-10-25). Retrieval-augmented question answering over PDFs and other documents with citations; uses LiteLLM so the model provider is configurable, and supports local embedding models. It is a candidate for checking a detected pattern against her corpus before the evidence-graph lookup, or for building graph entries. It is actively maintained and has a heavier dependency set (litellm, tantivy, pydantic).

AI-scientist and closed-loop frameworks, 2025 to 2026. Robin (`https://github.com/Future-House/robin`, Apache-2.0, last commit 2026-04-21) is a multi-agent discovery system whose README says the literature agents and the data-analysis step need a paid Edison platform API key. Agent Laboratory (`https://github.com/SamuelSchmidgall/AgentLaboratory`, MIT, last commit 2025-08-20) describes itself as LLM agents acting as research assistants; details beyond the README title are [unverified]. AI Scientist v2 (`https://github.com/SakanaAI/AI-Scientist-v2`, last commit 2025-12-19) uses "The AI Scientist Source Code License v1.0", a responsible-AI licence with use restrictions, not an OSI licence. In behavioural science, Brondetta and Musslick (ICML 2026, "Automated Prototyping of Behavioral Experiments with Large Language Models") close a loop between an LLM scientist and simulated LLM participants, and Chandramouli, Kachergis and Jagadish (arXiv 2604.25521, April 2026) combine LLM theory agents with information-theoretic experiment design in simulation; neither page links code, and neither involves human participants or a literature graph. None of these fields a survey to real members and returns to a literature check, so her loop remains an unfilled niche. [inference]

## 7. Recommendation

1. Do not make AutoRA a production dependency. The core is MIT and works, but it is dormant, pins numpy 1.x, and its orchestration is an in-process loop with pickle files.
2. Port the design. Keep AutoRA's three role names (experimentalist, experiment runner, theorist) and the state-plus-delta contract so the kit is recognisable to researchers and an adapter stays trivial.
3. Ignore the shipped theorists (BMS, BSR, DARTS), the samplers, the Firebase runner and `autodoc` for now. Revisit the Prolific manager only if paid panels are wanted.
4. Cover the gaps AutoRA leaves with other tools: HypoGeniC's pattern for hypothesis generation, PaperQA2 for literature checks, catsim or mirtCAT for adaptive item selection.
5. If code is copied from `state.py`, keep the MIT notice.

First three things a coding agent should do:

1. Write `research_loop/state.py`: a pydantic `LoopState` and `Delta` with a per-field merge policy (extend, append, replace) and an `apply(state, delta)` function, plus the step contract `step(state) -> Delta`. Port five or six of AutoRA's doctest cases as unit tests (extend a list, replace a value, unknown key warns, chained deltas). Persist one row per loop cycle and make every Pub/Sub event carry a delta.
2. Define the three role interfaces and their event mapping as JSON Schema shared by Python and Genkit: experimentalist (`gap.identified` in, design plus pull-request URL out), experiment runner split into non-blocking `publish()` and `collect()` with the status machine `awaiting_approval / fielding / closed`, target n, deadline and timeout, and theorist (data reference in, `pattern.detected` out).
3. Build a synthetic dry-run harness: a `synthetic_survey_runner` that generates responses with a planted pattern, in the spirit of `autora-synthetic`, and a CI test that runs the whole loop in a plain for-loop and asserts that the planted pattern is detected and the next draft targets the planted gap. Here, and only here, optionally add `autora-core` as a dev extra to prove the steps also run under `on_state`.

## Sources

Cloned and read (all under `https://github.com/AutoResearch/`): `autora`, `autora-core`, `autora-synthetic`, `autora-workflow`, `autora-experiment-runner-firebase-prolific`, `autora-experiment-runner-experimentation-manager-firebase`, `autora-experiment-runner-recruitment-manager-prolific`, `autora-theorist-bms`, `autora-theorist-darts`, `autora-experimentalist-novelty`, `autora-experimentalist-falsification`, `autora-experimentalist-model-disagreement`, `autora-experimentalist-uncertainty`, `autora-experimentalist-bandit-random`, `autodoc`, `autora-user-cookiecutter`, `SweetBean`. Local copies: `(local clone) `. Read in depth: `autora-core`, the three runner repos, the `autora` docs and the BMS regressor. Skimmed for signatures, metadata and file layout only: the rest (the uncertainty, falsification and bandit-random experimentalists were cloned but their code was not read).

Cloned and read for section 6 (local copies in `(local clone) alt/`): `https://github.com/douglasrizzo/catsim`, `https://github.com/philchalmers/mirtCAT`, `https://github.com/campsych/concerto-platform`, `https://github.com/ChicagoHAI/hypothesis-generation`, `https://github.com/Future-House/paper-qa`, `https://github.com/Future-House/robin`, `https://github.com/SakanaAI/AI-Scientist-v2`, `https://github.com/SamuelSchmidgall/AgentLaboratory`.

PyPI JSON metadata (`https://pypi.org/pypi/<name>/json`) for: autora, autora-core, autora-synthetic, autora-workflow, the three experiment-runner packages, autora-theorist-bms, autora-theorist-darts, autora-theorist-bsr, autora-experimentalist-model-disagreement, autora-doc, sweetbean, catsim, hypogenic, paper-qa, numpy.

Pages opened: `https://autoresearch.github.io/autora`, `https://icml.cc/virtual/2026/73542`, `https://www.alphaxiv.org/abs/2604.25521`. Two web searches were run for 2025 to 2026 closed-loop behavioural research frameworks.

Could not open: `https://joss.theoj.org/papers/10.21105/joss.06839` (blocked by the network proxy), `https://arxiv.org/abs/2603.20988` and `https://arxiv.org/abs/2510.13011` (fetch not permitted), and the GitHub REST API (stars, issues, organisation repo list). Not read: the React client template that claims Firestore slots, `autora-theorist-bsr`, and the remaining experimentalist packages (inequality, nearest-value, leverage, mixture, prediction-filter).
