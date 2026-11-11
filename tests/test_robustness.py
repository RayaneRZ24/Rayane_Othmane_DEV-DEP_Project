import asyncio
from unittest.mock import Mock
from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy.exc import OperationalError

from smartops.api import create_app


def test_oversized_offsets_and_event_cursors_are_rejected_before_reaching_sql():
    engine = Mock()
    engine.connect.side_effect = RuntimeError("private")
    identifier = uuid4()
    with TestClient(create_app(engine=engine, worker_enabled=False)) as client:
        assert client.get(f"/api/v1/runs/{identifier}/alerts?offset=3000000000").status_code == 422
        too_big = client.get(f"/api/v1/runs/{identifier}/events", headers={"Last-Event-ID": str(2**70)})
        assert too_big.status_code == 409


def test_read_failure_does_not_interrupt_the_active_run():
    engine = Mock()
    engine.connect.side_effect = RuntimeError("private")
    app = create_app(engine=engine, worker_enabled=False)
    with TestClient(app) as client:
        manager = app.state.replay
        manager.alerts = Mock(side_effect=OperationalError("sql", {}, Exception("driver")))
        manager.interrupt = Mock()
        response = client.get(f"/api/v1/runs/{uuid4()}/alerts")
        assert response.status_code == 503
        manager.interrupt.assert_not_called()


def test_worker_survives_unexpected_errors():
    engine = Mock()
    engine.connect.side_effect = RuntimeError("private")
    calls = {"tick": 0}

    def flaky_tick():
        calls["tick"] += 1
        raise ValueError("unexpected")

    async def scenario():
        app = create_app(engine=engine)
        async with app.router.lifespan_context(app):
            app.state.replay.tick = flaky_tick
            app.state.replay.interrupt = Mock()
            await asyncio.sleep(0.5)
        return calls["tick"]

    assert asyncio.run(scenario()) >= 2
