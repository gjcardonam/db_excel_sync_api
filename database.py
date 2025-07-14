
from sqlalchemy import create_engine

def create_pg_engine(config: dict):
    url = (
        f"postgresql+psycopg2://{config['user']}:{config['password']}@"
        f"{config['host']}:{config['port']}/{config['database']}"
    )
    return create_engine(url)
