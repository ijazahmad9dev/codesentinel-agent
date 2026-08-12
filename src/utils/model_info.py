"""
Extracts which model actually produced an AI message, from
response_metadata. Provider-specific key names vary slightly, so this
checks the common ones.
"""
from langchain_core.messages import AIMessage

def get_model_name(message) -> str | None:
    return (
        getattr(message, "response_metadata", {}).get("model_name")
        or getattr(message, "response_metadata", {}).get("model")
        or getattr(message, "additional_kwargs", {}).get("model")
    )

def collect_models_used(messages) -> list[str]:
    seen = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue
        name = get_model_name(msg)
        if name and name not in seen:
            seen.append(name)
    return seen