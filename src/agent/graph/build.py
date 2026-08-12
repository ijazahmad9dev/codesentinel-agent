from langgraph.graph import StateGraph, START, END

from src.agent.graph.state import GraphState
from src.agent.graph.nodes import (
    planner_node,
    coding_agent_node,
    aggregate_node,
    route_after_coding,
)


def build_graph():
    graph = StateGraph(GraphState)
    graph.add_node("planner", planner_node)
    graph.add_node("coding_agent", coding_agent_node)
    graph.add_node("aggregate", aggregate_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "coding_agent")
    graph.add_conditional_edges(
        "coding_agent",
        route_after_coding,
        {"coding_agent": "coding_agent", "aggregate": "aggregate"},
    )
    graph.add_edge("aggregate", END)

    return graph.compile()