"""
Coding-agent graph nodes: the main subtask loop, plus the two fix nodes
triggered by a failing test or a failing review. All three wrap the
same underlying coding agent from src/agent/core.py - only invocation
context and looping/budget logic live here.
"""

from langgraph.errors import GraphRecursionError

from src.agent.core import build_coding_agent
from src.agent.graph.state import GraphState
from src.agent.graph.planner.plan_store import write_plan
from src.agent import tools as agent_tools
from src.executor.sandbox import CodeSandbox
from src.utils.error_tracker import ErrorTracker
from src.utils.model_info import collect_models_used

sandbox = CodeSandbox()


def _tracker_for(state: GraphState) -> ErrorTracker:
    return ErrorTracker(state["project"], state["language"], CodeSandbox())


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
    """
    Checks the attempt budget BEFORE starting the next subtask or
    handing off to the tester. Without this, a plan could keep running
    every remaining step (and then a full tester round) even after the
    budget was already exhausted, since current_index/len(subtasks)
    alone doesn't know anything about attempts spent.
    """
    if _tracker_for(state).is_exhausted():
        return "final_aggregate"
    if state["current_index"] < len(state["subtasks"]):
        return "coding_agent"
    return "tester"


def _run_fix(state: GraphState, failure_output: str, reason: str) -> dict:
    agent_tools.set_current_project(state["project"], state["language"])
    agent = build_coding_agent()

    context = (
        f"A {reason} just reported a problem with this project. "
        f"Here is the real output:\n\n{failure_output}\n\n"
        f"Investigate and fix the actual application code causing this - "
        f"do not just modify tests to make them pass unless the test "
        f"itself is genuinely wrong. Use edit_code_in_file for targeted "
        f"fixes where possible. This is part of an automated pipeline - "
        f"do not ask whether to continue."
    )

    models = []
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": context}]},
            config={"recursion_limit": 25},
        )
        models = collect_models_used(result["messages"])
        fix_summary = result["messages"][-1].content
    except GraphRecursionError:
        fix_summary = "Fix attempt did not converge in time."
    except Exception as e:
        fix_summary = f"Fix attempt failed unexpectedly: {e}"

    return {
        "results": state["results"] + [f"Fix ({reason}): {fix_summary}"],
        "models_used": state["models_used"] + models,
    }


def fix_from_tests_node(state: GraphState) -> dict:
    return _run_fix(state, state["test_output"], "failing test")


def fix_from_review_node(state: GraphState) -> dict:
    return _run_fix(state, state["review_output"], "code review")