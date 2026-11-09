"""Central configuration.

All settings come from environment variables (or a local `.env`), never from
hard-coded values — see AGENTS.md rule 6 (secrets never touch git). Import the
singleton `settings` anywhere instead of reading os.environ directly.
"""

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_DEMO_ON = {"1", "true", "yes", "on"}
_DEMO_OFF = {"", "0", "false", "no", "off"}


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

    # Offline demo switch (WOHNIQ_DEMO). True forces demo mode even if DATABASE_URL is
    # set; see `demo_mode` for the full precedence. Empty/unset means "not forced".
    wohniq_demo: bool = False

    @field_validator("wohniq_demo", mode="before")
    @classmethod
    def _parse_demo_flag(cls, value: object) -> bool:
        """Accept 1/0, true/false, yes/no, on/off, or empty; reject anything else.

        Rejecting typos (e.g. "ture") matters here: silently reading them as "off"
        would send a demo laptop to the live database.
        """
        if isinstance(value, bool):
            return value
        text = str(value).strip().lower()
        if text in _DEMO_ON:
            return True
        if text in _DEMO_OFF:
            return False
        raise ValueError(
            f"WOHNIQ_DEMO must be 1/0, true/false, yes/no, on/off, or empty; got {value!r}"
        )

    @property
    def is_production(self) -> bool:
        return self.environment.lower() in {"prod", "production"}

    @property
    def demo_mode(self) -> bool:
        """Offline demo: serve bundled fixtures, make no DB/Gemini/transit/OSM calls.

        Precedence (first match wins):
          1. WOHNIQ_DEMO=1  -> demo, even when DATABASE_URL is set (the URL is ignored).
          2. DATABASE_URL empty -> demo (also the case with no .env and nothing exported).
          3. otherwise -> live.
        WOHNIQ_DEMO=0 does not force live mode: without a DATABASE_URL there is no
        database to be live against. Deployments that inject DATABASE_URL as a real env
        var (e.g. Railway, no .env file) stay live.
        """
        return self.demo_mode_reason is not None

    @property
    def demo_mode_reason(self) -> str | None:
        """Why demo mode is on (for startup logs), or None when running live."""
        if self.wohniq_demo:
            if self.database_url.strip():
                return "WOHNIQ_DEMO=1 overrides DATABASE_URL, which is set but ignored"
            return "WOHNIQ_DEMO=1"
        if not self.database_url.strip():
            return "DATABASE_URL is empty"
        return None

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
