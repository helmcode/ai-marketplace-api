from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    # Database
    database_url: str = "postgresql://localhost:5432/ai_marketplace"

    # Auth0
    auth0_domain: str = ""
    auth0_audience: str = ""
    auth0_client_id: str = ""

    # Digital Ocean
    digitalocean_token: str = ""
    digitalocean_system_ssh_key_id: str = ""  # ID of the SSH key in DO for system access
    system_ssh_private_key_path: str = ""  # Path to the private key file on this server

    # Encryption
    encryption_key: str = ""

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # CORS (comma-separated URLs)
    cors_origins: str = "http://localhost:5173,http://localhost:3000"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
