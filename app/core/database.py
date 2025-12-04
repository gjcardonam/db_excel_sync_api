from sqlalchemy import create_engine
from sqlalchemy.engine import URL

def create_pg_engine(config: dict, **kwargs):
    url = URL.create(
        drivername="postgresql+psycopg2",
        username=config["user"],
        password=config["password"],
        host=config["host"],
        port=config["port"],
        database=config["database"],
    )
    return create_engine(url, pool_pre_ping=True, **kwargs)
