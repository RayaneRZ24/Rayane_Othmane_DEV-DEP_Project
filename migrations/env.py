from alembic import context

from smartops.config import Settings
from smartops.storage import Base, make_engine

config = context.config


def migrate(connection):
    context.configure(connection=connection, target_metadata=Base.metadata)
    with context.begin_transaction():
        context.run_migrations()


if context.is_offline_mode():
    context.configure(
        url=Settings().database_url.get_secret_value(), target_metadata=Base.metadata,
        literal_binds=True, dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()
elif config.attributes.get("connection") is not None:
    migrate(config.attributes["connection"])
else:
    engine = make_engine(Settings().database_url.get_secret_value())
    try:
        with engine.connect() as connection:
            migrate(connection)
    finally:
        engine.dispose()
