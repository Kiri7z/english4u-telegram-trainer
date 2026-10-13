import os
from sqlalchemy import URL, create_engine
from sqlalchemy.orm import declarative_base, sessionmaker


def required_env(name):
    value = os.environ.get(name, "")
    if not value or value.startswith("REPLACE_WITH_"):
        raise RuntimeError(f"Required environment variable {name} is missing or a placeholder")
    return value


DATABASE_URL = URL.create(
    "postgresql+psycopg2",
    username=required_env("DB_USER"),
    password=required_env("DB_PASSWORD"),
    host=os.environ.get("DB_HOST", "postgres"),
    port=int(os.environ.get("DB_PORT", "5432")),
    database=required_env("DB_NAME"),
)
engine = create_engine(DATABASE_URL, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()
