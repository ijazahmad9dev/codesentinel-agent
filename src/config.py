import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass
class Settings:
    OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "https://machinery-push-causes-regression.trycloudflare.com")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "qwen3-coder-next:latest")
    ERROR_LOG_PATH: str = os.getenv("ERROR_LOG_PATH", "data/errors.json")
    EXECUTION_TIMEOUT: int = int(os.getenv("EXECUTION_TIMEOUT", "15"))
    WORKSPACE_DIR: str = os.getenv("WORKSPACE_DIR", "workspace")
    MAX_AGENT_ITERATIONS: int = int(os.getenv("MAX_AGENT_ITERATIONS", "10"))
    EXECUTOR_URL: str = os.getenv("EXECUTOR_URL", "http://localhost:8000")
    DATA_DIR: str = os.getenv("DATA_DIR", "data")


settings = Settings()