from langgraph.errors import GraphRecursionError

from src.agent.core import build_coding_agent
from src.agent.graph.state import GraphState
from src.agent.graph.planner.plan_store import write_plan
from src.agent import tools as agent_tools
from src.executor.sandbox import CodeSandbox
from src.utils.model_info import collect_models_used

sandbox = CodeSandbox()


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


def fix_node(state: GraphState) -> dict:
    """
    Invoked when the tester reports a failure. Same coding agent,
    different context: given the real test failure output and asked to
    fix the specific broken code.
    """
    agent_tools.set_current_project(state["project"], state["language"])
    agent = build_coding_agent()

    context = (
        f"The test suite for this project just failed. Here is the real "
        f"output from running the tests:\n\n{state['test_output']}\n\n"
        f"Investigate the failure(s) and fix the actual application code "
        f"causing them - do not just modify the tests to make them pass "
        f"unless the test itself is genuinely wrong. Use edit_code_in_file "
        f"for targeted fixes where possible. This is part of an automated "
        f"pipeline - do not ask whether to continue."
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
        "results": state["results"] + [f"Fix attempt (round {state['test_round']}): {fix_summary}"],
        "models_used": state["models_used"] + models,
    }