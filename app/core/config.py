from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    service_name: str = "aixiaomi-llm-proxy"
    database_url: str = "sqlite:///./llm_proxy.db"
    mock_mode: bool = True
    default_text_model: str = "mock-text-llm-v1"
    default_vlm_model: str = "mock-image-vlm-v1"
    default_business_scenario: str = "moments_album"
    deepseek_base_url: str = "https://api.deepseek.com"
    deepseek_api_key: str | None = None
    deepseek_default_model: str = "deepseek-v4-flash"
    moments_copywriting_provider: str = "deepseek"
    moments_copywriting_model: str = "deepseek-v4-flash"
    fallback_to_mock_on_provider_error: bool = True
    request_timeout_seconds: float = 30
    deepseek_cost_yuan_per_1k_input_tokens: float = 0
    deepseek_cost_yuan_per_1k_output_tokens: float = 0
    decision_input_token_cost: int = 1200
    decision_output_token_cost: int = 300
    copy_input_token_cost: int = 900
    copy_output_token_cost: int = 500
    charged_tokens_per_text_request: int = 1200
    charged_tokens_per_copy_request: int = 12000
    charged_tokens_per_vlm_image: int = 2500

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


@lru_cache
def get_settings() -> Settings:
    return Settings()
