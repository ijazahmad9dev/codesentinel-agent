from langgraph.graph import StateGraph, START, END

from src.agent.graph.state import GraphState
from src.agent.graph.planner.node import planner_node
from src.agent.graph.coding.node import coding_agent_node, route_after_coding, fix_node
from src.agent.graph.tester.node import tester_node
from src.agent.graph.common.aggregate import aggregate_node, route_after_test


def build_graph():
    graph = StateGraph(GraphState)

    graph.add_node("planner", planner_node)
    graph.add_node("coding_agent", coding_agent_node)
    graph.add_node("tester", tester_node)
    graph.add_node("fix", fix_node)
    graph.add_node("final_aggregate", aggregate_node)

    graph.add_edge(START, "planner")
    graph.add_edge("planner", "coding_agent")
    graph.add_conditional_edges(
        "coding_agent", route_after_coding,
        {"coding_agent": "coding_agent", "aggregate": "tester"},
    )
    graph.add_conditional_edges(
        "tester", route_after_test,
        {"final_aggregate": "final_aggregate", "fix": "fix"},
    )
    graph.add_edge("fix", "tester")
    graph.add_edge("final_aggregate", END)

    return graph.compile()