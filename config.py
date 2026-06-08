import os
from functools import lru_cache
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    # App Settings
    APP_NAME: str = "Userbot Migrasi Backend"
    APP_ENV: str = "production"
    
    # Telegram Credentials (Wajib dari Environment Variables)
    API_ID: int
    API_HASH: str
    
    # CORS Settings (Tidak menggunakan wildcard * di production)
    CORS_ORIGINS: str = "https://your-cloudflare-pages-domain.pages.dev"
    
    # Security Token untuk WebSocket
    WS_TOKEN: str = "default_secret_token"
    
    # Path Session Telethon
    SESSION_NAME: str = "userbot_session"

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True

@lru_cache()
def get_settings() -> Settings:
    return Settings()