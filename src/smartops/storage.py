from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, Uuid, create_engine, func, select
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
        return True
    except Exception:
        # Never return connection strings, SQL, or driver errors to the browser.
        return False
