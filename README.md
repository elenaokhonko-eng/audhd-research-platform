# Research Multi-Agent System (CrewAI)

A production-grade, modular multi-agent system built using [CrewAI](https://github.com/crewAIPlatform/crewAI) to automate deep-dive academic and market research. This project uses a strictly sequential, five-stage pipeline to gather raw data, verify factual grounding (detect and completely eliminate hallucinations, fake DOIs, or statistical drifts), draft comprehensive articles, and editorially polish and certify reports into ready-to-publish, certified Markdown files.

---

## 🗺️ System Architecture & Workflow

This system employs a **Sequential Process** workflow, ensuring that the outputs of preceding agents flow directly as inputs/context into subsequent tasks.

```text
 ┌────────────────────────┐
 │   Target Topic Input   │
 └───────────┬────────────┘
             ▼
 ┌────────────────────────┐
 │ Senior Research Analyst│ ──► [research_task] Focus: Fact-gathering, citations, & synthesis
 └───────────┬────────────┘
             ▼
 ┌────────────────────────┐
 │ Hallucination Verifier │ ──► [verify_research_summary_task] Focus: Verify DOIs, quotes, NLI, stats
 └───────────┬────────────┘
             ▼
 ┌────────────────────────┐
 │    Technical Writer    │ ──► [draft_task] Focus: Narrative structure, clarity, & markdown draft
 └───────────┬────────────┘
             ▼
 ┌────────────────────────┐
 │  Editorial Specialist  │ ──► [review_task] Focus: Grammar, tone, formatting, & polishing
 └───────────┬────────────┘
             ▼
 ┌────────────────────────┐
 │ Hallucination Verifier │ ──► [verify_final_report_task] Focus: final numerical & quotation certification
 └───────────┬────────────┘
             ▼
 ┌────────────────────────┐
 │ final_research_report  │ ──► [Output File] Certified, publication-ready markdown article
 └────────────────────────┘
```

---

## 📂 Project Structure

```text
research_multi_agent_system/
├── README.md                # Project documentation and usage guide
├── requirements.txt         # Project python dependencies
├── .env.example             # Template for environment keys (OpenAI, Serper, etc.)
├── config/
│   ├── agents.yaml          # Declarative definition of agent personas (role, goal, backstory)
│   └── tasks.yaml           # Declarative definition of task details and outputs
└── src/
    ├── __init__.py          # Marks src as a package
    ├── crew.py              # Crew definition class linking configurations and decorators
    └── main.py              # CLI entry point to configure inputs and kickoff the system
```

---

## ⚙️ Installation & Setup

Follow these steps to set up and run the multi-agent system on your machine:

### 1. Clone or Navigate to the Folder
Ensure you are in the `research_multi_agent_system` directory:
```bash
cd research_multi_agent_system
```

### 2. Set Up a Virtual Environment
Create and activate a clean Python virtual environment:
```bash
# Create
python -m venv .venv

# Activate (Linux/macOS)
source .venv/bin/activate

# Activate (Windows)
.venv\Scripts\activate
```

### 3. Install Dependencies
Install all required python packages:
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` file to `.env` and fill in your details:
```bash
cp .env.example .env
```
Open `.env` and add your **Kimi Code API Key** and endpoint details:
```env
OPENAI_API_KEY=your-kimi-code-api-key-here
OPENAI_API_BASE=https://api.kimi.com/coding/v1
OPENAI_MODEL_NAME=kimi-for-coding
```
*(This maps Moonshot's specialized **Kimi Code** API—supporting standard models like `kimi-for-coding` and the flagship `k3` reasoning engine—via their dedicated coding gateway.)*



---

## 🚀 Running the Crew

To kickoff the multi-agent system, execute the main driver script:

```bash
python src/main.py
```

### Passing Topic via Arguments
You can also run the script and pass the research topic directly through command-line arguments:

```bash
python src/main.py "quantum computing breakthroughs in 2026"
```

Once execution begins:
1. The **Senior Research Analyst** will perform the research.
2. The **Technical Writer** will draft the report.
3. The **Editorial Specialist** will polish the draft.
4. The final polished result will be outputted and saved as **`final_research_report.md`** in your active directory!

---

## 🛠️ Customizing Agents and Tasks

One of the key benefits of this modular setup is that you don't need to write Python code to tweak agent personas or tasks.

- **To modify agent personalities**: Open `config/agents.yaml` and edit the `role`, `goal`, and `backstory` parameters.
- **To modify task descriptions/expectations**: Open `config/tasks.yaml` and edit the `description` or `expected_output` parameters.
- **To add new agents**: 
  1. Define the agent inside `config/agents.yaml`.
  2. Define their corresponding task inside `config/tasks.yaml`.
  3. Wire them up in `src/crew.py` using `@agent` and `@task` decorators, then add them to the `Crew()` constructor.
