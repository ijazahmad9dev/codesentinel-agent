def describe_models_used(messages) -> list[str]:
    """
    Inspects every AI-generated message in the conversation and reports
    which model actually produced it, based on response_metadata that
    each provider (Ollama, Groq) attaches to its output. Lets you see
    in the terminal whether a run used the primary model throughout, or
    silently fell back to Groq at some point.
    """
    from langchain_core.messages import AIMessage

    seen = []
    for msg in messages:
        if not isinstance(msg, AIMessage):
            continue

        model_name = (
            msg.response_metadata.get("model_name")
            or msg.response_metadata.get("model")
            or msg.additional_kwargs.get("model")
        )
        if model_name and model_name not in seen:
            seen.append(model_name)

    return seen