"""Application configuration via environment variables."""

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    # Application
    environment: str = "development"
    debug: bool = False
    service_name: str = "productivity-service"

    # AWS
    aws_region: str = "us-east-1"

    # CORS
    cors_origins: list[str] = ["*"]

    # OmniFocus Mail Drop
    omnifocus_mail_drop_address: str = ""  # User's OmniFocus Mail Drop email
    ses_sender_email: str = ""  # Verified SES sender email

    # Bedrock - Claude Haiku 4.5 with cross-region inference
    bedrock_model_id: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"

    class Config:
        env_prefix = "PRODUCTIVITY_"
        case_sensitive = False


settings = Settings()
