import os
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task

# Initialize environment tools if needed
# from crewai_tools import SerperDevTool
# search_tool = SerperDevTool()

@CrewBase
class ResearchMultiAgentCrew():
    """Research Multi-Agent System using CrewAI"""

    # Path to YAML configuration files
    agents_config = '../config/agents.yaml'
    tasks_config = '../config/tasks.yaml'

    # Resolve relative paths relative to this file's folder
    current_dir = os.path.dirname(os.path.abspath(__file__))
    agents_config = os.path.join(current_dir, '..', 'config', 'agents.yaml')
    tasks_config = os.path.join(current_dir, '..', 'config', 'tasks.yaml')

    @agent
    def analyst(self) -> Agent:
        return Agent(
            config=self.agents_config['analyst'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def researcher(self) -> Agent:
        return Agent(
            config=self.agents_config['researcher'],
            # tools=[search_tool], # Uncomment if SerperDevTool is configured in .env
            verbose=True,
            allow_delegation=False
        )

    @agent
    def writer(self) -> Agent:
        return Agent(
            config=self.agents_config['writer'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def editor(self) -> Agent:
        return Agent(
            config=self.agents_config['editor'],
            verbose=True,
            allow_delegation=False
        )

    @agent
    def hallucination_verifier(self) -> Agent:
        return Agent(
            config=self.agents_config['hallucination_verifier'],
            verbose=True,
            allow_delegation=False
        )

    @task
    def formalize_hypothesis_task(self) -> Task:
        return Task(
            config=self.tasks_config['formalize_hypothesis_task'],
            human_input=True # CP-01 HITL Checkpoint: Pauses execution to gather researcher feedback and approval before proceeding
        )

    @task
    def research_task(self) -> Task:
        return Task(
            config=self.tasks_config['research_task'],
        )

    @task
    def verify_research_summary_task(self) -> Task:
        return Task(
            config=self.tasks_config['verify_research_summary_task'],
        )

    @task
    def draft_task(self) -> Task:
        return Task(
            config=self.tasks_config['draft_task'],
        )

    @task
    def review_task(self) -> Task:
        return Task(
            config=self.tasks_config['review_task'],
        )

    @task
    def verify_final_report_task(self) -> Task:
        return Task(
            config=self.tasks_config['verify_final_report_task'],
            output_file='final_research_report.md' # Saves the final verified & certified output automatically
        )

    @crew
    def crew(self) -> Crew:
        """Creates the Research Multi-Agent Crew"""
        return Crew(
            agents=[
                self.analyst(),
                self.researcher(),
                self.hallucination_verifier(),
                self.writer(),
                self.editor()
            ],
            tasks=[
                self.formalize_hypothesis_task(),
                self.research_task(),
                self.verify_research_summary_task(),
                self.draft_task(),
                self.review_task(),
                self.verify_final_report_task()
            ],
            process=Process.sequential, # Forces tasks to run sequentially with zero leakage
            verbose=True,
        )
