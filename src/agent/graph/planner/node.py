from src.agent.graph.state import GraphState
from src.agent.graph.planner.logic import generate_plan
from src.agent.graph.planner.plan_store import write_plan
from src.executor.sandbox import CodeSandbox

sandbox = CodeSandbox()


def planner_node(state: GraphState) -> dict:
    subtasks, model_name = generate_plan(state["task"])

    write_plan(sandbox, state["project"], state["language"], state["task"], subtasks, completed_index=-1)

    return {
        "subtasks": subtasks,
        "current_index": 0,
        "results": [],
        "models_used": [model_name] if model_name else [],
        "test_status": "pending",
        "test_output": "",
        "test_round": 0,
    }