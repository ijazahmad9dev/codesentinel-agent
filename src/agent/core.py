from langchain.agents import create_agent
from langchain_ollama import ChatOllama

from src.agent.tools import (
    execute_code,
    execute_project_command,
    write_code_to_file,
    list_workspace_projects,
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
        execute_code,
        execute_project_command,
        write_code_to_file,
        list_workspace_projects,
    ]

    return create_agent(model=model, tools=tools, system_prompt=SYSTEM_PROMPT)