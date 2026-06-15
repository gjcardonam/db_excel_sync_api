from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.engine import URL


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


@lru_cache(maxsize=None)
def _cached_engine(host, port, database, user, password):
    return create_pg_engine(
        {
            "host": host,
            "port": port,
            "database": database,
            "user": user,
            "password": password,
        }
    )


def get_engine(config: dict):
    """
    Return a cached engine for the given DB config, creating it once per unique
    connection target. Reusing the engine preserves the connection pool across
    requests instead of opening (and leaking) a fresh engine every time.
    """
    return _cached_engine(
        config["host"],
        config["port"],
        config["database"],
        config["user"],
        config["password"],
    )
