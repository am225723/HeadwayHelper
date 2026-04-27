import os
from functools import lru_cache
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = "development"
    app_name: str = "Clinical AI Webapp"
    debug: bool = True
    log_level: str = "info"
    database_url: str = "sqlite:///./clinical_ai.db"
    jwt_secret_key: str = "change-me"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = Field(default=1440, validation_alias="JWT_EXPIRE_MINUTES")
    allowed_origins: str = "http://localhost:3000,http://127.0.0.1:3000"
    google_drive_root_folder_id: str | None = None
    google_service_account_json: str | None = None
    drive_scan_interval: int = 300
    ai_provider: str = "perplexity"
    perplexity_api_key: str | None = None
    perplexity_model: str = "sonar"
    perplexity_fallback_prompt_for_new_key: bool = True
    gemini_api_key: str | None = None
    gemini_model: str = "gemini-2.5-pro"
    openai_api_key: str | None = None
    openai_model: str | None = None
    summary_template_name: str = "Clinical_Summary_Template.html"
    session_template_name: str = "Session_Notes_Template.html"
    treatment_template_name: str = "Treatment_Plan_Template.html"
    pdf_output_tmp_dir: str = "/tmp/clinical-ai"
    default_payer: str = "Aetna"
    eval_comparison_enabled: bool = True
    summary_auto_save_pdf: bool = True
    session_note_default_mode: str = "draft"
    treatment_plan_default_mode: str = "review"
    enable_safer_preview_flow: bool = True
    enable_diagnostics: bool = True
    enable_healthchecks: bool = True
    enable_render_debug_logs: bool = True
    save_template_render_logs: bool = True
    save_placeholder_diagnostics: bool = True
    admin_email: str = "aleix@drzelisko.com"
    admin_password: str = ""
    admin_full_name: str = "Aleixander Puerta"
    run_seeds_on_startup: bool = False
    seed_reimbursement_rates: bool = True
    seed_default_service_types: bool = True
    seed_default_classification_rules: bool = True
    seed_default_workflow_settings: bool = True
    seed_default_templates: bool = True
    reimbursement_table_path: str = "app/reimbursement_rates.example.json"

    model_config = SettingsConfigDict(env_file=None if os.getenv("VERCEL") else ".env", extra="ignore")

    @property
    def cors_origins(self) -> list[str]:
        return [origin.strip() for origin in self.allowed_origins.split(",") if origin.strip()]

    @property
    def access_token_expire_minutes(self) -> int:
        return self.jwt_expire_minutes

    @property
    def sync_database_url(self) -> str:
        url = self.database_url.strip()

        if url.startswith("postgresql+asyncpg://"):
            return url.replace("postgresql+asyncpg://", "postgresql+psycopg://", 1)

        if url.startswith("postgresql://"):
            return url.replace("postgresql://", "postgresql+psycopg://", 1)

        if url.startswith("postgres://"):
            return url.replace("postgres://", "postgresql+psycopg://", 1)

        return url

    def startup_warnings(self) -> list[str]:
        warnings: list[str] = []
        if self.app_env.lower() == "production":
            if self.database_url.startswith("sqlite"):
                warnings.append("DATABASE_URL should point to Postgres in production.")
            if self.jwt_secret_key in {"change-me", "", "replace-with-a-long-random-secret"}:
                warnings.append("JWT_SECRET_KEY must be set to a long random secret in production.")
            if not self.google_service_account_json or not self.google_drive_root_folder_id:
                warnings.append("Google Drive service account and root folder are required for production storage.")
            if self.ai_provider.lower() == "perplexity" and not self.perplexity_api_key:
                warnings.append("PERPLEXITY_API_KEY is required when AI_PROVIDER=perplexity.")
        return warnings


@lru_cache
def get_settings() -> Settings:
    return Settings()
