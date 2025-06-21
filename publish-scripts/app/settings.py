from pydantic import Field
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    hassio_token: str = Field(default="", description="Home Assistant token")
    ha_base_url: str = Field(default="http://supervisor/core/api", description="Home Assistant URL")
    ngrok_auth_token: str = Field(default="", description="Ngrok authentication token")
    port: int = Field(default=8099, description="Port for the FastAPI app and ngrok tunnel to forward to")

    class Config:
        # Get the current file's directory and use parent directory for .env
        import os
        env_file = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        env_file_encoding = "utf-8"


def get_settings(**overrides):
    return Settings(**overrides)