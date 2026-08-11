"""
Agent construction using LangChain's `create_agent`, with automatic
fallback from local Ollama to Groq's hosted API if Ollama is unreachable
(e.g. a broken tunnel URL). Uses ModelFallbackMiddleware rather than
.with_fallbacks() - the latter is currently incompatible with
create_agent (raises AttributeError: 'RunnableWithFallbacks' object has
no attribute 'startswith').
"""

from langchain.agents import create_agent
from langchain.agents.middleware import ModelFallbackMiddleware
from langchain_ollama import ChatOllama
from langchain_groq import ChatGroq

from src.agent.tools import (
    write_code_to_file,
    edit_code_in_file,
    execute_project_command,
    list_project_files,
)
from src.agent.prompts import SYSTEM_PROMPT
from src.config import settings


def build_agent():
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

    fallback_middleware = ModelFallbackMiddleware(fallback_model)

    tools = [write_code_to_file, edit_code_in_file, execute_project_command, list_project_files]

    return create_agent(
        model=primary_model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
        middleware=[fallback_middleware],
    )