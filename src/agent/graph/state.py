from typing import TypedDict


class GraphState(TypedDict):
    task: str
    project: str
    language: str
    subtasks: list[str]
    current_index: int
    results: list[str]
    models_used: list[str]
    final_summary: str
    test_status: str
    test_output: str
    test_round: int
    review_status: str
    review_output: str
    review_round: int