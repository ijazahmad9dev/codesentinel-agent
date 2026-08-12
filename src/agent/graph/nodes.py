"""
Graph node implementations. coding_agent_node wraps the existing,
unchanged coding agent from src/agent/core.py - this file only controls
invocation (once per subtask, with plan context) and progress tracking,
never touches the coding agent's internals.
"""

from langgraph.errors import GraphRecursionError

from src.agent.core import build_coding_agent
from src.agent.graph.planner import generate_plan
from src.agent.graph.state import GraphState
from src.agent import tools as agent_tools
from src.executor.sandbox import CodeSandbox
from src.utils.model_info import collect_models_used
from src.utils.plan_store import write_plan

sandbox = CodeSandbox()


def planner_node(state: GraphState) -> dict:
    subtasks, model_name = generate_plan(state["task"])

    write_plan(sandbox, state["project"], state["language"], state["task"], subtasks, completed_index=-1)

    return {
        "subtasks": subtasks,
        "current_index": 0,
        "results": [],
        "models_used": [model_name] if model_name else [],
    }


def coding_agent_node(state: GraphState) -> dict:
    idx = state["current_index"]
    subtask = state["subtasks"][idx]

    agent_tools.set_current_project(state["project"], state["language"])
    agent = build_coding_agent()

    plan_listing = "\n".join(f"{i + 1}. {t}" for i, t in enumerate(state["subtasks"]))
    context = (
        f"Overall goal: {state['task']}\n\n"
        f"Full plan ({len(state['subtasks'])} steps):\n{plan_listing}\n\n"
        f"Your current step ({idx + 1} of {len(state['subtasks'])}): {subtask}\n\n"
        f"This is part of an automated multi-step pipeline. Complete this "
        f"step fully and do NOT ask the user whether to continue - the "
        f"next step runs automatically once you finish. If earlier steps "
        f"already created files in this project, use list_project_files "
        f"or view_file to see the current state before making changes."
    )

    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": context}]},
            config={"recursion_limit": 25},
        )
        final_message = result["messages"][-1].content
        models = collect_models_used(result["messages"])
    except GraphRecursionError:
        final_message = f"Step {idx + 1} did not converge in time and was stopped."
        models = []
    except Exception as e:
        final_message = f"Step {idx + 1} failed unexpectedly: {e}"
        models = []

    write_plan(
        sandbox, state["project"], state["language"], state["task"],
        state["subtasks"], completed_index=idx,
    )

    return {
        "current_index": idx + 1,
        "results": state["results"] + [f"Step {idx + 1}: {subtask}\n{final_message}"],
        "models_used": state["models_used"] + models,
    }


def route_after_coding(state: GraphState) -> str:
    if state["current_index"] < len(state["subtasks"]):
        return "coding_agent"
    return "aggregate"


def aggregate_node(state: GraphState) -> dict:
    return {"final_summary": "\n\n".join(state["results"])} 