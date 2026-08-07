"""
Agent construction using LangChain's `create_agent`.
"""

from langchain.agents import create_agent
from langchain_ollama import ChatOllama

from src.agent.tools import (
    execute_python_code,
    write_code_to_file,
    log_execution_error,
    clear_execution_error,
)
from src.agent.prompts import SYSTEM_PROMPT
from src.config import settings


def build_agent():
    model = ChatOllama(
        model=settings.MODEL_NAME,
        base_url=settings.OLLAMA_BASE_URL,
        temperature=0,
    )

    tools = [
        execute_python_code,
        write_code_to_file,
        log_execution_error,
        clear_execution_error,
    ]

    agent = create_agent(
        model=model,
        tools=tools,
        system_prompt=SYSTEM_PROMPT,
    )
    return agent