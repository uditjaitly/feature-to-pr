from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    anthropic_api_key: str
    github_token: str
    clone_depth: int = 1
    max_repo_size_mb: int = 500
    model: str = "claude-sonnet-4-6"

    class Config:
        env_file = ".env"


settings = Settings()
