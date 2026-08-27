
from pydantic_settings import BaseSettings  # Changed from pydantic import BaseSettings
from pydantic import Field, model_validator
from typing import Dict, List
import os
from pathlib import Path

from app.prompts.badge_options import (
    CRITERION_TEMPLATES as DEFAULT_CRITERION_TEMPLATES,
    LEVEL_DESCRIPTIONS as DEFAULT_LEVEL_DESCRIPTIONS,
    STYLE_DESCRIPTIONS as DEFAULT_STYLE_DESCRIPTIONS,
    SUPPORTED_LANGUAGES as DEFAULT_SUPPORTED_LANGUAGES,
    TONE_DESCRIPTIONS as DEFAULT_TONE_DESCRIPTIONS,
)


DEFAULT_SYSTEM_PROMPT_PATH = (
    Path(__file__).resolve().parents[1] / "prompts" / "badge_system_prompt.txt"
)


def _parse_cors_origins(raw: str) -> List[str]:
    """Parse a comma-separated list of allowed CORS origins into a clean list."""
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


class Settings(BaseSettings):
    # Ollama Configuration
    OLLAMA_API_URL: str = os.getenv("OLLAMA_API_URL", "http://localhost:11434/api/generate")
    MODEL_NAME: str = os.getenv("MODEL_NAME", "phi4-mini:3.8b-q4_K_M")
    MODEL_KEEP_ALIVE: str = os.getenv("MODEL_KEEP_ALIVE", "30m")
    MODEL_SYSTEM_PROMPT_PATH: str = os.getenv(
        "MODEL_SYSTEM_PROMPT_PATH",
        str(DEFAULT_SYSTEM_PROMPT_PATH),
    )
    MODEL_TEMPERATURE: float = 0.10
    MODEL_TOP_P: float = 0.9
    MODEL_TOP_K: int = 25
    MODEL_NUM_PREDICT: int = 1024
    MODEL_REPEAT_PENALTY: float = 1.05
    MODEL_NUM_CTX: int = 6144
    MODEL_SEED: str = ""
    # Badge Image Service Configuration
    BADGE_IMAGE_SERVICE_URL: str = os.getenv("BADGE_IMAGE_SERVICE_URL", "http://localhost:3001")

    # CORS Configuration
    # Comma-separated allowlist of origins permitted to call the API.
    # Explicit origins are required because allow_credentials=True is incompatible
    # with a wildcard ("*") origin.
    CORS_ORIGINS_STR: str = os.getenv("CORS_ORIGINS_STR", "http://localhost:3000")
    CORS_ORIGINS: List[str] = Field(default_factory=list)

    # Open Badge v3 Issuer Configuration
    # Base URL used to build the achievement image `id` (an IRI in the OBv3 spec).
    BADGE_ISSUER_URL: str = os.getenv("BADGE_ISSUER_URL", "http://localhost:8000")

    # Logging Configuration
    ENABLE_LOG_BASE64_DATA: bool = False

    # Model Configuration
    MODEL_CONFIG: Dict = Field(default_factory=dict)
    
    # Asset paths - COMMENTED OUT (moved to external image service)
    # ASSETS_PATH: str = "assets/"
    # ICONS_PATH: str = "assets/icons/"
    # LOGOS_PATH: str = "assets/logos/"
    # FONTS_PATH: str = "assets/fonts/"
    
    # NLTK Configuration
    NLTK_AVAILABLE: bool = True

    # LAiSER Skill Extraction Configuration
    LAISER_MODEL_ID: str = os.getenv("LAISER_MODEL_ID", "bert-base-uncased")
    LAISER_HF_TOKEN: str = os.getenv("LAISER_HF_TOKEN", "")
    LAISER_USE_GPU: bool = os.getenv("LAISER_USE_GPU", "false").lower() == "true"
    LAISER_TOP_K: int = int(os.getenv("LAISER_TOP_K", "10"))

    # Prompt options are kept in a dependency-free module so evaluation tools
    # can reuse the exact production text without importing Pydantic/FastAPI.
    STYLE_DESCRIPTIONS: Dict = DEFAULT_STYLE_DESCRIPTIONS
    TONE_DESCRIPTIONS: Dict = DEFAULT_TONE_DESCRIPTIONS
    LEVEL_DESCRIPTIONS: Dict = DEFAULT_LEVEL_DESCRIPTIONS
    CRITERION_TEMPLATES: Dict = DEFAULT_CRITERION_TEMPLATES
    SUPPORTED_LANGUAGES: Dict = DEFAULT_SUPPORTED_LANGUAGES

    model_config = {"env_file": ".env", "extra": "ignore"}

    @model_validator(mode="after")
    def _derive_cors_origins(self) -> "Settings":
        """Derive settings assembled from individual environment variables."""
        self.CORS_ORIGINS = _parse_cors_origins(self.CORS_ORIGINS_STR)
        self.MODEL_CONFIG = {
            "temperature": self.MODEL_TEMPERATURE,
            "top_p": self.MODEL_TOP_P,
            "top_k": self.MODEL_TOP_K,
            "num_predict": self.MODEL_NUM_PREDICT,
            "repeat_penalty": self.MODEL_REPEAT_PENALTY,
            "num_ctx": self.MODEL_NUM_CTX,
        }
        if self.MODEL_SEED.strip():
            self.MODEL_CONFIG["seed"] = int(self.MODEL_SEED)
        return self

settings = Settings()
