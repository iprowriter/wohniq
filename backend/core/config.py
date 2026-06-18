"""Central configuration.

All settings come from environment variables (or a local `.env`), never from
hard-coded values — see AGENTS.md rule 6 (secrets never touch git). Import the
singleton `settings` anywhere instead of reading os.environ directly.
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",  # tolerate unrelated env vars
    )

    environment: str = "dev"

    # Gemini (LLM + embeddings). Empty by default so the app boots without a key;
    # the LLM client checks for presence before making calls.
    gemini_api_key: str = ""

    # Supabase / Postgres
    database_url: str = ""
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_role_key: str = ""

    # Pexels (image seeding)
    pexels_api_key: str = ""

    # Comma-separated allowed origins for CORS (the frontend).
    frontend_origins: str = "http://localhost:3000"

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.frontend_origins.split(",") if o.strip()]

    @property
    def sqlalchemy_url(self) -> str:
        """DATABASE_URL coerced to the psycopg (v3) driver.

        SQLAlchemy defaults `postgresql://` to psycopg2, which we don't install.
        Pinning `+psycopg` here means a plain Supabase URL just works.
        """
        url = self.database_url
        if url.startswith("postgresql://"):
            return "postgresql+psycopg://" + url[len("postgresql://") :]
        if url.startswith("postgres://"):
            return "postgresql+psycopg://" + url[len("postgres://") :]
        return url


settings = Settings()
