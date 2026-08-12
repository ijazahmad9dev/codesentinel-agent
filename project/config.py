from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite:///./blog.db"
    app_name: str = "Blog API"
    debug: bool = False


settings = Settings()
