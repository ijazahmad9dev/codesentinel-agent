import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://joke-abilities-assistant-ticket.trycloudflare.com")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3-coder-next:latest")
    GROQ_API_KEY: str = os.getenv("GROQ_API_KEY", "")
    GROQ_MODEL_NAME: str = os.getenv("GROQ_MODEL_NAME", "openai/gpt-oss-120b")
    E2B_API_KEY: str = os.getenv("E2B_API_KEY", "")
    E2B_TIMEOUT_SECONDS: int = int(os.getenv("E2B_TIMEOUT_SECONDS", "3600"))
    DATA_DIR: str = os.getenv("DATA_DIR", "data")
    EXECUTION_TIMEOUT: int = int(os.getenv("EXECUTION_TIMEOUT", "60"))
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))


settings = Settings()