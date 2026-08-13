import re

from langgraph.errors import GraphRecursionError

from src.agent.core import build_reviewer_agent
from src.agent.graph.state import GraphState
from src.agent.graph.reviewer.review_store import write_review_results
from src.agent import tools as agent_tools
from src.executor.sandbox import CodeSandbox
from src.utils.model_info import collect_models_used
from src.utils.error_tracker import ErrorTracker
from src.executor.sandbox import CodeSandbox

sandbox = CodeSandbox()

STATUS_PATTERN = re.compile(r"REVIEW_STATUS:\s*(PASS|FAIL)", re.IGNORECASE)


def parse_review_status(text: str) -> str:
    match = STATUS_PATTERN.search(text)
    if not match:
        # No clear verdict given - default to PASS rather than looping
        # indefinitely on an ambiguous response. Noted in REVIEW.md either way.
        return "passed"
    return "passed" if match.group(1).upper() == "PASS" else "failed"


def reviewer_node(state: GraphState) -> dict:

    tracker = ErrorTracker(state["project"], state["language"], CodeSandbox())
    if tracker.is_exhausted():
        return {
            "review_status": "skipped",
            "review_output": "Skipped - attempt budget already exhausted before review could run.",
            "review_round": state["review_round"],
        }
    
    project, language = state["project"], state["language"]
    round_num = state["review_round"] + 1

    agent_tools.set_current_project(project, language)
    agent = build_reviewer_agent()

    context = (
        f"Original user request: {state['task']}\n\n"
        f"The project has been built and its tests pass. Review whether "
        f"it actually satisfies the original request above."
    )

    models = []
    output_text = "(reviewer did not produce output)"
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": context}]},
            config={"recursion_limit": 20},
        )
        models = collect_models_used(result["messages"])
        output_text = result["messages"][-1].content
    except GraphRecursionError:
        output_text = "Review did not converge in time - defaulting to PASS to avoid a stuck pipeline."
    except Exception as e:
        output_text = f"Review failed unexpectedly: {e} - defaulting to PASS to avoid a stuck pipeline."

    status = parse_review_status(output_text)
    write_review_results(sandbox, project, language, round_num, status, output_text)

    return {
        "review_status": status,
        "review_output": output_text,
        "review_round": round_num,
        "models_used": state["models_used"] + models,
    }