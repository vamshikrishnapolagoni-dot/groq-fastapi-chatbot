import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "AI Research Assistant"
    DEBUG: bool = False
    PORT: int = 8000
    HOST: str = "0.0.0.0"

    # API Keys
    GROQ_API_KEY: str
    TAVILY_API_KEY: str

    # Database
    # Local fallback for Dev, render/supabase in production
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/research_assistant"

    # Vector Storage
    CHROMA_PERSIST_DIR: str = "./chroma_db"

    # Authentication - Clerk
    CLERK_FRONTEND_API: Optional[str] = None
    CLERK_API_KEY: Optional[str] = None
    CLERK_JWT_ISSUER: Optional[str] = None # e.g. https://clerk.yourdomain.com or https://your-app.clerk.accounts.dev
    # For JWT verification, we can fetch JWKS. Clerk JWKS URIs are standard:
    # https://api.clerk.com/v1/jwks or https://<your-clerk-frontend-api>/.well-known/jwks.json
    CLERK_JWKS_URL: Optional[str] = None

    # Storage
    SUPABASE_URL: Optional[str] = None
    SUPABASE_KEY: Optional[str] = None
    SUPABASE_BUCKET: str = "research-documents"

    # CORS
    ALLOWED_ORIGINS: str = "*"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Instantiate settings
settings = Settings()
