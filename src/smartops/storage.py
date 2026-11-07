from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import BigInteger, DateTime, Float, ForeignKey, Integer, String, Uuid, create_engine, func, select
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class IntegrationProbe(Base):
    __tablename__ = "integration_probes"

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )


class ReplayRun(Base):
    __tablename__ = "replay_runs"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    scenario_id: Mapped[UUID] = mapped_column(Uuid, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="created")
    cursor_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    speed: Mapped[float] = mapped_column(Float)
    active_slot: Mapped[int | None] = mapped_column(Integer, nullable=True, unique=True)
    detector_profile: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    detector_name: Mapped[str] = mapped_column(String(40), default="robust-mad-v1", server_default="robust-mad-v1")
    detector_state: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    analyzed_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ReplayOperation(Base):
    __tablename__ = "replay_operations"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    request_hash: Mapped[str] = mapped_column(String(64))
    response: Mapped[dict] = mapped_column(JSONB)


class RunEvent(Base):
    __tablename__ = "run_events"
    sequence: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("replay_runs.id"), index=True)
    payload: Mapped[dict] = mapped_column(JSONB)


class Alert(Base):
    __tablename__ = "alerts"
    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    run_id: Mapped[UUID] = mapped_column(ForeignKey("replay_runs.id"), index=True)
    feature_id: Mapped[str] = mapped_column(String(100))
    feature_label: Mapped[str] = mapped_column(String(150))
    resource: Mapped[str] = mapped_column(String(20))
    status: Mapped[str] = mapped_column(String(20))
    start_index: Mapped[int] = mapped_column(BigInteger)
    detected_index: Mapped[int] = mapped_column(BigInteger)
    last_anomalous_index: Mapped[int] = mapped_column(BigInteger)
    closed_index: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    peak_score: Mapped[float] = mapped_column(Float)
    evidence: Mapped[dict] = mapped_column(JSONB)


def make_engine(url: str) -> Engine:
    return create_engine(
        url, pool_pre_ping=True, connect_args={"connect_timeout": 3},
        pool_size=5, max_overflow=0,
    )


def database_ready(engine: Engine) -> bool:
    """Check both the connection and the first migrated application table."""
    try:
        with engine.connect() as connection:
            connection.execute(select(IntegrationProbe.id).limit(1))
            connection.execute(select(ReplayRun.id).limit(1))
            connection.execute(select(Alert.id).limit(1))
        return True
    except Exception:
        # Never return connection strings, SQL, or driver errors to the browser.
        return False
