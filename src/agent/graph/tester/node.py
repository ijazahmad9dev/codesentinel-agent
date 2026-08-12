"""
Tester node. The tester AGENT writes the test files (LLM-driven), but
the pass/fail decision is made deterministically by running the real
test command directly against the sandbox and checking its actual exit
code - never inferred from the model's own conversational output.
"""

from langgraph.errors import GraphRecursionError

from src.agent.core import build_tester_agent
from src.agent.graph.state import GraphState
from src.agent.graph.tester.test_store import write_test_results
from src.agent import tools as agent_tools
from src.executor.sandbox import CodeSandbox
from src.utils.model_info import collect_models_used

sandbox = CodeSandbox()

TEST_COMMANDS = {
    "python": "pip install pytest -q --disable-pip-version-check && python3 -m pytest tests/ -v",
    "node": "npm install --silent && npm test --silent",
}


def tester_node(state: GraphState) -> dict:
    project, language = state["project"], state["language"]
    round_num = state["test_round"] + 1

    agent_tools.set_current_project(project, language)
    agent = build_tester_agent()

    context = (
        f"The project for this task has been built: {state['task']}\n\n"
        f"Write a real test suite for it now, inside tests/."
    )
    if state["test_output"]:
        context += (
            f"\n\nNote: a previous test round failed and the coding agent "
            f"attempted a fix. Re-check your existing tests still make "
            f"sense given any changes, and add/adjust tests if needed."
        )

    models = []
    try:
        result = agent.invoke(
            {"messages": [{"role": "user", "content": context}]},
            config={"recursion_limit": 20},
        )
        models = collect_models_used(result["messages"])
    except GraphRecursionError:
        pass
    except Exception:
        pass

    command = TEST_COMMANDS.get(language, TEST_COMMANDS["python"])
    run_result = sandbox.run(project, language, command, timeout=120)

    status = "passed" if run_result.success else "failed"
    output = f"$ {command}\n\nSTDOUT:\n{run_result.stdout}\n\nSTDERR:\n{run_result.stderr}"

    write_test_results(sandbox, project, language, round_num, status, output)

    return {
        "test_status": status,
        "test_output": output,
        "test_round": round_num,
        "models_used": state["models_used"] + models,
    }