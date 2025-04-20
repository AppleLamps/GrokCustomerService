from pydantic_settings import BaseSettings
from functools import lru_cache
from typing import Optional
import os

class Settings(BaseSettings):
    API_KEY: str
    MODEL_NAME: str = "gpt-4.1"  # default model
    MAX_TOKENS: int = 8000
    TEMPERATURE: float = 0.7
    
    # RAG settings
    EMBEDDING_MODEL: str = "text-embedding-3-small"
    DOCS_DIR: str = os.path.join("data", "grok_docs")
    VECTOR_STORE_PATH: str = os.path.join("data", "vector_store")
    CHUNK_SIZE: int = 1000
    CHUNK_OVERLAP: int = 150
    TOP_K_RESULTS: int = 3

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"

@lru_cache()
def get_settings() -> Settings:
    return Settings()

# Validate settings at startup
settings = get_settings() 