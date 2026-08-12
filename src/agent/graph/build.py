from langgraph.graph import StateGraph, START, END

from src.agent.graph.state import GraphState
from src.agent.graph.planner.node import planner_node
from src.agent.graph.coding.node import (
    coding_agent_node, route_after_coding, fix_from_tests_node, fix_from_review_node,
)
from src.agent.graph.tester.node import tester_node
from src.agent.graph.reviewer.node import reviewer_node
from src.agent.graph.common.aggregate import (
    aggregate_node, route_after_test, route_after_review, route_after_fix,
)


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("planner", planner_node)
    graph.add_node("coding_agent", coding_agent_node)
    graph.add_node("tester", tester_node)
    graph.add_node("fix_from_tests", fix_from_tests_node)
    graph.add_node("reviewer", reviewer_node)
    graph.add_node("fix_from_review", fix_from_review_node)
    graph.add_node("final_aggregate", aggregate_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "coding_agent")

    graph.add_conditional_edges(
            "coding_agent", route_after_coding,
            {"coding_agent": "coding_agent", "tester": "tester", "final_aggregate": "final_aggregate"},
        )

    graph.add_conditional_edges(
        "tester", route_after_test,
        {"reviewer": "reviewer", "fix_from_tests": "fix_from_tests", "final_aggregate": "final_aggregate"},
    )

    graph.add_conditional_edges(
        "fix_from_tests", route_after_fix,
        {"tester": "tester", "final_aggregate": "final_aggregate"},
    )

    graph.add_conditional_edges(
        "reviewer", route_after_review,
        {"fix_from_review": "fix_from_review", "final_aggregate": "final_aggregate"},
    )

    graph.add_conditional_edges(
        "fix_from_review", route_after_fix,
        {"tester": "tester", "final_aggregate": "final_aggregate"},
    )

    graph.add_edge("final_aggregate", END)

    return graph.compile()