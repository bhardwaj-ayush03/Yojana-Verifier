from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    tinyfish_api_key: str | None = None
    tinyfish_search_url: str = "https://api.search.tinyfish.ai"
    tinyfish_fetch_url: str = "https://api.fetch.tinyfish.ai"
    tinyfish_agent_url: str = "https://agent.tinyfish.ai/v1/automation/run"
    llm_api_key: str | None = None
    llm_model: str | None = None
    groq_api_key: str | None = None
    groq_model: str = "openai/gpt-oss-120b"
    # Live discovery is the default. Seeded results require an explicit opt-in.
    yojana_mock_mode: bool = False
    yojana_max_agent_runs: int = Field(default=3, ge=0)
    yojana_cache_ttl_hours: int = Field(default=24, ge=1)

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    @property
    def effective_llm_key(self) -> str | None:
        return self.groq_api_key or self.llm_api_key

    @property
    def effective_llm_model(self) -> str:
        return self.groq_model if self.groq_api_key else (self.llm_model or self.groq_model)


def get_settings() -> Settings:
    return Settings()
