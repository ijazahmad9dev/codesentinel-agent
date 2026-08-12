"""
Model construction, shared between the coding agent (tool-using,
create_agent) and the planner (plain completion, no tools).
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq

from src.agent.tools import (
    write_code_to_file,
    edit_code_in_file,
    view_file,
    execute_project_command,
    list_project_files,
)
from src.agent.prompts import SYSTEM_PROMPT
from src.config import settings


def build_chat_models():
    """Returns (primary, fallback) model instances - Ollama primary, Groq fallback."""
    primary_model = ChatOllama(
        model=settings.MODEL_NAME,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0,
    )
    fallback_model = ChatGroq(
        model=settings.GROQ_MODEL_NAME,
        api_key=settings.GROQ_API_KEY,
        temperature=0,
    )
    return primary_model, fallback_model


def build_coding_agent():
    """
    The existing tool-using agent (write_code_to_file, edit_code_in_file,
    view_file, execute_project_command, list_project_files), unchanged
    from before this refactor - only how it's invoked (once per subtask,
    from a graph node) is new.
    """
    primary_model, fallback_model = build_chat_models()
    fallback_middleware = ModelFallbackMiddleware(fallback_model)

    tools = [write_code_to_file, edit_code_in_file, view_file, execute_project_command, list_project_files]

    return create_agent(
        model=primary_model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[fallback_middleware],
    )

def build_tester_agent():
    from src.agent.graph.tester.prompt import TESTER_SYSTEM_PROMPT

    primary_model, fallback_model = build_chat_models()
    fallback_middleware = ModelFallbackMiddleware(fallback_model)

    tools = [write_code_to_file, edit_code_in_file, view_file, execute_project_command, list_project_files]

    return create_agent(
        model=primary_model,
        tools=tools,
        system_prompt=TESTER_SYSTEM_PROMPT,
        middleware=[fallback_middleware],
    )

def build_planner_model():
    """
    Plain chat model with fallback - NOT wrapped in create_agent, since
    the planner has no tools. .with_fallbacks() is safe to use directly
    here (the earlier AttributeError issue was specific to combining it
    with create_agent).
    """
    primary_model, fallback_model = build_chat_models()
    return primary_model.with_fallbacks([fallback_model])


# Backward-compatible alias, in case anything still imports build_agent
build_agent = build_coding_agent