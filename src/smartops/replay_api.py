import asyncio
import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Header, Query, Request
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from smartops.replay import ReplayError

router = APIRouter(prefix="/api/v1", tags=["Relecture"])


class CreateRun(BaseModel):
    model_config = ConfigDict(extra="forbid")
    request_id: UUID
    scenario_id: UUID
    speed: float = Field(default=10, ge=1, le=60, allow_inf_nan=False)
    detector_name: Literal["robust-mad-v1", "pca-joint-v1"] = "robust-mad-v1"


class Command(BaseModel):
    model_config = ConfigDict(extra="forbid")
    command_id: UUID
    action: Literal["start", "pause", "resume", "stop"]


def call(request, method, *args):
    manager = request.app.state.replay
    try:
        return getattr(manager, method)(*args)
    except SQLAlchemyError:
        manager.interrupt()
        raise ReplayError(503, "STORAGE_UNAVAILABLE", "Le stockage est temporairement indisponible.") from None


@router.get("/scenarios")
def scenarios(request: Request):
    return {"items": [s.public() for s in request.app.state.replay.registry.scenarios.values()]}


@router.post("/runs", responses={201: {"description": "Exécution créée"}, 200: {"description": "Requête déjà traitée"}})
def create(request: Request, body: CreateRun):
    result, created = call(request, "create", body.request_id, body.scenario_id, body.speed, body.detector_name)
    return JSONResponse(result, status_code=201 if created else 200)


@router.get("/runs")
def runs(request: Request):
    return {"items": call(request, "list_runs")}


@router.get("/runs/{identifier}")
def read(request: Request, identifier: UUID):
    return call(request, "read", identifier)


@router.post("/runs/{identifier}/commands")
def command(request: Request, identifier: UUID, body: Command):
    return call(request, "command", identifier, body.command_id, body.action)


@router.get("/runs/{identifier}/metrics")
def metrics(request: Request, identifier: UUID, feature: str,
            from_index: int | None = Query(default=None, ge=0),
            to_index: int | None = Query(default=None, ge=0),
            limit: int = Query(default=500, ge=1, le=500), cursor: str | None = Query(default=None, max_length=4000)):
    return call(request, "page", identifier, feature, from_index, to_index, limit, cursor)


@router.get("/runs/{identifier}/events")
async def events(request: Request, identifier: UUID, last_event_id: str | None = Header(default=None),
                 samples: int | None = Query(default=None, ge=1, le=10)):
    after = None
    if last_event_id is not None:
        try:
            after = int(last_event_id)
            if after < 1:
                raise ValueError()
        except ValueError:
            raise ReplayError(409, "INVALID_EVENT_CURSOR", "Le curseur de connexion est invalide.") from None
    initial = await run_in_threadpool(call, request, "events", identifier, after)

    async def generate():
        pending, position, count, heartbeats = initial, after, 0, 0
        while not await request.is_disconnected():
            for sequence, payload in pending:
                position, count = sequence, count + 1
                yield f"id: {sequence}\nevent: run.updated\ndata: {json.dumps(payload)}\n\n"
                if (samples and count >= samples) or payload["status"] in {"stopped", "completed", "failed", "interrupted"}:
                    return
            await asyncio.sleep(.25)
            try:
                pending = await run_in_threadpool(call, request, "events", identifier, position)
            except ReplayError:
                yield 'event: run.unavailable\ndata: {}\n\n'
                return
            heartbeats += 1
            if heartbeats % 60 == 0:
                yield ": heartbeat\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream", headers={
        "Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no",
    })


@router.get("/runs/{identifier}/alerts")
def alerts(request: Request, identifier: UUID, offset: int = Query(default=0, ge=0),
           limit: int = Query(default=100, ge=1, le=500),
           resource: Literal["cpu", "memory", "disk", "network"] | None = None):
    return call(request, "alerts", identifier, offset, limit, resource)
