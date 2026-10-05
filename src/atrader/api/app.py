"""The FastAPI application: `create_app()` wires the services and the security rules.

Local by default (docs/06): it listens on loopback, answers only to known Host names,
and lets only the web app's origins read or change anything."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse

from atrader import __version__
from atrader.api.market import Market
from atrader.api.reports import ReportLibrary
from atrader.api.routes import ApiError, Services, changes, router
from atrader.api.runs import RunManager
from atrader.api.watchlist import Watchlist
from atrader.config import Settings, get_settings
from atrader.data.providers.nse_instruments import InstrumentMaster
from atrader.graph.research_graph import ResearchGraph
from atrader.graph.run_registry import RunRegistry

# The only model a client sends; its defaults really are optional.
_INPUT_MODELS = {"RunBody", "HTTPValidationError", "ValidationError"}


def _response_schemas(schema: dict[str, Any]) -> dict[str, Any]:
    """Describe responses as they are: every field of a response model is always sent, so
    none is optional (pydantic marks fields with defaults as optional). The report endpoint
    leaves out the price series, which is served by the bars endpoint, so the schema does too."""
    schemas = schema.get("components", {}).get("schemas", {})
    for dropped_from, field in (("EvidencePack", "bars"), ("IndexSeries", "closes")):
        schemas.get(dropped_from, {}).get("properties", {}).pop(field, None)
    for name, definition in schemas.items():
        if name not in _INPUT_MODELS and "properties" in definition:
            definition["required"] = list(definition["properties"])
    return schema


def create_app(
    settings: Settings | None = None, *,
    load_master: Callable[[], InstrumentMaster] | None = None,
    make_graph: Callable[..., ResearchGraph] | None = None,
) -> FastAPI:
    """`load_master` and `make_graph` exist so tests can run without the network."""
    settings = settings or get_settings()
    settings.ensure_dirs()

    app = FastAPI(title="aTrader API", version=__version__, docs_url="/v1/docs",
                  redoc_url=None, openapi_url="/v1/openapi.json")
    app.state.services = Services(
        settings=settings,
        market=Market(settings, load_master),
        reports=ReportLibrary(settings.reports_dir),
        runs=RunManager(settings, make_graph),
        watchlist=Watchlist(settings.db_path),
        registry=RunRegistry(settings.db_path),
    )

    app.add_middleware(
        CORSMiddleware, allow_origins=settings.web_origins,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Last-Event-ID"])
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.api_hosts)

    @app.exception_handler(ApiError)
    def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse({"code": exc.code, "message": exc.message}, status_code=exc.status)

    app.include_router(router)
    app.include_router(changes)

    def openapi() -> dict[str, Any]:
        if app.openapi_schema is None:
            app.openapi_schema = _response_schemas(get_openapi(
                title=app.title, version=app.version, routes=app.routes))
        return app.openapi_schema

    app.openapi = openapi  # type: ignore[method-assign]
    return app
