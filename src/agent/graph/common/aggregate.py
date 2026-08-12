from src.agent.graph.state import GraphState
from src.utils.error_tracker import ErrorTracker
from src.executor.sandbox import CodeSandbox


def aggregate_node(state: GraphState) -> dict:
    return {"final_summary": "\n\n".join(state["results"])}


def _tracker_for(state: GraphState) -> ErrorTracker:
    return ErrorTracker(state["project"], state["language"], CodeSandbox())


def route_after_test(state: GraphState) -> str:
    if state["test_status"] != "passed":
        return "final_aggregate" if _tracker_for(state).is_exhausted() else "fix_from_tests"
    return "reviewer"


def route_after_review(state: GraphState) -> str:
    if state["review_status"] != "passed":
        return "final_aggregate" if _tracker_for(state).is_exhausted() else "fix_from_review"
    return "final_aggregate"


def route_after_fix(state: GraphState) -> str:
    """Gate BEFORE re-running the tester, so an exhausted budget stops
    the pipeline immediately after a fix attempt instead of burning one
    more full tester round first."""
    return "final_aggregate" if _tracker_for(state).is_exhausted() else "tester"