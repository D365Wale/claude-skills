"""Environment-driven settings. Every external dependency is optional:
without keys, ATLAS runs on local fallbacks (hash embedder, in-memory
vector store, template codegen) so the full pipeline works offline.
"""
import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    # D365 F&O connection (client-credentials grant)
    d365_base_url: str = field(default_factory=lambda: os.environ.get("D365_BASE_URL", ""))
    d365_tenant_id: str = field(default_factory=lambda: os.environ.get("D365_TENANT_ID", ""))
    d365_client_id: str = field(default_factory=lambda: os.environ.get("D365_CLIENT_ID", ""))
    d365_client_secret: str = field(
        default_factory=lambda: os.environ.get("D365_CLIENT_SECRET", "")
    )

    # Optional upgrades — leave unset to use local fallbacks
    jina_api_key: str = field(default_factory=lambda: os.environ.get("JINA_API_KEY", ""))
    groq_api_key: str = field(default_factory=lambda: os.environ.get("GROQ_API_KEY", ""))
    database_url: str = field(default_factory=lambda: os.environ.get("DATABASE_URL", ""))

    embedding_dim: int = 256  # local hash embedder dim; Jina v3 overrides to 1024

    @property
    def d365_configured(self) -> bool:
        return bool(
            self.d365_base_url
            and self.d365_tenant_id
            and self.d365_client_id
            and self.d365_client_secret
        )


def load_settings() -> Settings:
    return Settings()
