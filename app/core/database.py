from sqlalchemy import create_engine
from sqlalchemy.engine import URL

# Cache of engines keyed by connection target, so the connection pool is reused
# across requests instead of opening (and leaking) a fresh engine every time.
_ENGINES: dict[tuple, "object"] = {}


def create_pg_engine(config: dict, **kwargs):
    """Create a brand new SQLAlchemy engine from a DB config dict."""
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )
    return create_engine(url, pool_pre_ping=True, **kwargs)


def get_engine(config: dict):
    """Return a cached engine for the given DB config, creating it once per target."""
    key = (
        config["host"],
        config["port"],
        config["database"],
        config["user"],
        config["password"],
    )
    engine = _ENGINES.get(key)
    if engine is None:
        engine = create_pg_engine(config)
        _ENGINES[key] = engine
    return engine


def dispose_all_engines() -> None:
    """Dispose every cached engine (and its pool). Call on application shutdown."""
    for engine in _ENGINES.values():
        engine.dispose()
    _ENGINES.clear()
