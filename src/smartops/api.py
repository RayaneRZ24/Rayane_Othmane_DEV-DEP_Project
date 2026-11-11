import asyncio
import json
import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from uuid import UUID, uuid4
from pathlib import Path

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.engine import Engine
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from smartops import __version__
from smartops.config import Settings
from smartops.storage import IntegrationProbe, database_ready, make_engine
from smartops.replay import ReplayError, ReplayManager
from smartops.replay_api import router as replay_router


logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("smartops")


class Health(BaseModel):
    status: str
    api: str = "available"
    database: str
    version: str = __version__
    checked_at: datetime


class ProbeResult(BaseModel):
    id: UUID
    created_at: datetime
    persisted: bool


def unavailable() -> HTTPException:
    return HTTPException(
        status_code=503,
        detail={"code": "DATABASE_UNAVAILABLE", "message": "Base de données ou migrations indisponibles."},
    )


def create_app(settings: Settings | None = None, engine: Engine | None = None,
               monitoring_dir: Path | None = None, worker_enabled: bool = True, monotonic=None) -> FastAPI:
    @asynccontextmanager
    async def lifespan(app: FastAPI):
        owned = engine is None
        resolved = settings or (Settings() if owned else None)
        app.state.engine = engine or make_engine(resolved.database_url.get_secret_value())
        root = monitoring_dir if monitoring_dir is not None else (resolved.monitoring_dir if resolved else Path("data/monitoring-smd"))
        options = {"monotonic": monotonic} if monotonic else {}
        app.state.replay = ReplayManager(app.state.engine, root, **options)
        if await run_in_threadpool(database_ready, app.state.engine):
            await run_in_threadpool(app.state.replay.recover)

        async def worker():
            while True:
                await asyncio.sleep(.1)
                try:
                    await run_in_threadpool(app.state.replay.tick)
                except asyncio.CancelledError:
                    raise
                except (SQLAlchemyError, ReplayError):
                    logger.exception("Replay worker: storage or replay error, interrupting the run")
                    await run_in_threadpool(app.state.replay.interrupt)
                except Exception:
                    # Never let an unexpected error silently kill the worker.
                    logger.exception("Replay worker: unexpected error, interrupting the run")
                    await run_in_threadpool(app.state.replay.interrupt)

        task = asyncio.create_task(worker()) if worker_enabled else None
        try:
            yield
        finally:
            if task:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            await run_in_threadpool(app.state.replay.interrupt)
            if owned:
                app.state.engine.dispose()

    app = FastAPI(title="SmartOps API", version=__version__, lifespan=lifespan)
    app.include_router(replay_router)

    @app.exception_handler(ReplayError)
    async def replay_error(request: Request, error: ReplayError):
        request_id = str(uuid4())
        logger.warning("%s %s -> %s %s [request_id=%s]", request.method, request.url.path, error.status, error.code, request_id)
        return JSONResponse(status_code=error.status, content={"error": {
            "code": error.code, "message": error.message, "request_id": request_id,
        }})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, error: StarletteHTTPException):
        detail = error.detail if isinstance(error.detail, dict) else {"code": "HTTP_ERROR", "message": str(error.detail)}
        request_id = str(uuid4())
        if error.status_code >= 500:
            logger.warning("%s %s -> %s [request_id=%s]", request.method, request.url.path, error.status_code, request_id)
        return JSONResponse(status_code=error.status_code, content={"error": {**detail, "request_id": request_id}})

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, error: RequestValidationError):
        return JSONResponse(status_code=422, content={"error": {
            "code": "INVALID_REQUEST", "message": "Les paramètres de la requête sont invalides.",
            "request_id": str(uuid4()),
        }})

    @app.get("/health", response_model=Health, responses={503: {"model": Health}})
    def health(request: Request):
        ready = database_ready(request.app.state.engine)
        payload = Health(
            status="healthy" if ready else "degraded",
            database="available" if ready else "unavailable",
            checked_at=datetime.now(timezone.utc),
        )
        return JSONResponse(status_code=200 if ready else 503, content=payload.model_dump(mode="json"))

    @app.post("/api/v1/system/probes", response_model=ProbeResult, status_code=201)
    def create_probe(request: Request):
        """Write a technical probe and verify its visibility in a new transaction."""
        db = request.app.state.engine
        try:
            with Session(db) as session:
                probe = IntegrationProbe()
                session.add(probe)
                session.flush()
                probe_id = probe.id
                session.commit()
            with Session(db) as session:
                saved = session.get(IntegrationProbe, probe_id)
                if saved is None:
                    raise unavailable()
                return ProbeResult(id=saved.id, created_at=saved.created_at, persisted=True)
        except SQLAlchemyError:
            raise unavailable() from None

    @app.get("/api/v1/system/events")
    async def events(request: Request, samples: int | None = Query(default=None, ge=1, le=10)):
        """Technical SSE stream in wall-clock time, separate from future replay events."""
        if not await run_in_threadpool(database_ready, request.app.state.engine):
            raise unavailable()

        def snapshot():
            with Session(request.app.state.engine) as session:
                return session.scalar(select(func.count()).select_from(IntegrationProbe))

        async def generate():
            sequence = 0
            while samples is None or sequence < samples:
                if await request.is_disconnected():
                    return
                try:
                    count = await run_in_threadpool(snapshot)
                except SQLAlchemyError:
                    yield 'event: system.unavailable\ndata: {"database":"unavailable"}\n\n'
                    return
                sequence += 1
                payload = json.dumps({
                    "sequence": sequence, "probe_count": count,
                    "emitted_at": datetime.now(timezone.utc).isoformat(),
                })
                yield f"event: system.snapshot\ndata: {payload}\n\n"
                if samples is None or sequence < samples:
                    await asyncio.sleep(1)

        return StreamingResponse(generate(), media_type="text/event-stream", headers={
            "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
        })

    return app


app = create_app()
