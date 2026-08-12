from src.agent.graph.state import GraphState


def aggregate_node(state: GraphState) -> dict:
    return {"final_summary": "\n\n".join(state["results"])}


def route_after_test(state: GraphState) -> str:
    from src.utils.error_tracker import ErrorTracker
    from src.executor.sandbox import CodeSandbox

    if state["test_status"] == "passed":
        return "final_aggregate"

    tracker = ErrorTracker(state["project"], state["language"], CodeSandbox())
    attempt = tracker.record_attempt()
    if attempt["global_limit_reached"]:
        return "final_aggregate"

    return "fix"