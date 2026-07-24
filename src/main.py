import os
import sys

from dotenv import load_dotenv

# Load this project's .env before importing CrewAI code
load_dotenv()

from langsmith.integrations.otel import OtelSpanProcessor
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.instrumentation.crewai import CrewAIInstrumentor
from opentelemetry.instrumentation.openai import OpenAIInstrumentor

# Configure OpenTelemetry
tracer_provider = trace.get_tracer_provider()

if not isinstance(tracer_provider, TracerProvider):
    tracer_provider = TracerProvider()
    trace.set_tracer_provider(tracer_provider)

tracer_provider.add_span_processor(OtelSpanProcessor())

# Instrument CrewAI and its OpenAI-compatible client
CrewAIInstrumentor().instrument(tracer_provider=tracer_provider)
OpenAIInstrumentor().instrument(tracer_provider=tracer_provider)

# Make the src directory importable
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import the crew only after tracing is configured
from crew import ResearchMultiAgentCrew


# Ensure standard OpenAI-compatible Base URL environment variables are mapped for CrewAI
if os.getenv("OPENAI_API_BASE"):
    os.environ["OPENAI_API_BASE"] = os.getenv("OPENAI_API_BASE")


def run():
    """
    Run the Research Multi-Agent Crew to execute the sequential research pipeline.
    """
    # Get topic from CLI arguments, or default to a cool subject if none provided
    if len(sys.argv) > 1:
        topic = " ".join(sys.argv[1:])
    else:
        topic = input("Enter the research topic: ").strip()
        if not topic:
            topic = "Artificial General Intelligence (AGI) and Safety Alignments"
            print(f"No topic provided. Defaulting to: '{topic}'")

    inputs = {
        'topic': topic
    }

    print("\n" + "="*60)
    print(f"🚀 Kicking off Multi-Agent Research System")
    print(f"🎯 Target Topic: '{topic}'")
    print(f"📊 Workflow Process: Sequential (Researcher -> Writer -> Editor)")
    print("="*60 + "\n")

    try:
        os.makedirs("artifacts", exist_ok=True)
        # Initialize and kickoff the crew
        crew_instance = ResearchMultiAgentCrew()
        result = crew_instance.crew().kickoff(inputs=inputs)

        print("\n" + "="*60)
        print("🎉 Multi-Agent Workflow Completed Successfully!")
        print("="*60)
        print(f"\n📂 Final Report saved to: 'final_research_report.md'")
        print("\n📄 Summary of results:")
        print(result)
        print("="*60 + "\n")

    except Exception as e:
        print(f"\n❌ Error occurred during crew execution: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    run()
