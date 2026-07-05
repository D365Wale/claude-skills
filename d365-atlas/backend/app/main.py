"""App factory. Providers resolve from environment at startup:
no keys -> local embedder + memory store + template codegen (fully offline);
keys present -> Jina / pgvector / Groq, same interfaces.
"""
from fastapi import FastAPI

from app import __version__
from app.ai.codegen import GroqCodegen, TemplateCodegen
from app.ai.embedder import make_embedder
from app.api import router
from app.config import load_settings
from app.store.vectorstore import make_store


def create_app() -> FastAPI:
    settings = load_settings()
    app = FastAPI(title="D365 ATLAS", version=__version__)
    app.state.settings = settings
    app.state.embedder = make_embedder(settings.jina_api_key)
    app.state.store = make_store(settings.database_url, dim=app.state.embedder.dim)
    app.state.codegen = TemplateCodegen()
    app.state.groq = GroqCodegen(settings.groq_api_key) if settings.groq_api_key else None
    app.state.docs_by_name = {}
    app.include_router(router)
    return app


app = create_app()
