from dataclasses import dataclass

from crewai import Agent, Crew, Process, Task


@dataclass(frozen=True, slots=True)
class AgentSpec:
    role: str
    goal: str
    backstory: str


SPECS = {
    "formalize": AgentSpec(
        "Scientific Hypothesis Analyst",
        "Turn a raw idea into operationalized, falsifiable H0/H1 hypotheses.",
        "You are rigorous about constructs, measurement, confounding, ethics, and uncertainty.",
    ),
    "synthesis": AgentSpec(
        "Evidence Synthesis Researcher",
        "Synthesize only the supplied source passages with traceable evidence identifiers.",
        "You never invent a paper, DOI, quotation, statistic, or evidence identifier.",
    ),
    "scientific_report": AgentSpec(
        "Scientific Report Author",
        "Produce a transparent scientific report from verified evidence only.",
        "You clearly separate evidence, interpretation, limitations, and future hypotheses.",
    ),
    "substack": AgentSpec(
        "Neurodivergence Science Communicator",
        "Adapt the approved report without weakening uncertainty or introducing facts.",
        "You write accessible, respectful science communication for a general audience.",
    ),
    "visuals": AgentSpec(
        "Scientific Visual Editor",
        "Design source-linked chart specifications and responsible editorial image proposals.",
        "Every visual has provenance, caption, alt text, and a clear evidence/illustration label.",
    ),
}


def run_agent_stage(kind: str, description: str, expected_output: str) -> str:
    spec = SPECS[kind]
    agent = Agent(role=spec.role, goal=spec.goal, backstory=spec.backstory, verbose=True, allow_delegation=False)
    task = Task(description=description, expected_output=expected_output, agent=agent)
    result = Crew(agents=[agent], tasks=[task], process=Process.sequential, verbose=True).kickoff()
    return str(result)
