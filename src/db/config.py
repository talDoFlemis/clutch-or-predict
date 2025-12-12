"""
Configuration module for database using Dynaconf.
"""

from pathlib import Path
from dynaconf import Dynaconf

# Get the directory where this config file is located
settings_dir = Path(__file__).parent

settings = Dynaconf(
    envvar_prefix="DB",
    settings_files=[
        settings_dir / "settings.yaml",
        settings_dir / ".secrets.yaml",
    ],
    environments=True,
    load_dotenv=True,
    merge_enabled=True,
)


def get_database_url() -> str:
    """
    Build the PostgreSQL database URL from configuration.

    Returns:
        str: The complete PostgreSQL database URL in the format:
             postgresql://user:password@host:port/dbname?sslmode=mode
    """
    user = settings.get("postgres.user", "postgres")
    password = settings.get("postgres.password", "")
    host = settings.get("postgres.host", "localhost")
    port = settings.get("postgres.port", 5432)
    dbname = settings.get("postgres.dbname", "postgres")
    sslmode = settings.get("postgres.sslmode", "prefer")

    # Build auth part
    auth = f"{user}"
    if password:
        auth = f"{user}:{password}"

    return f"postgresql://{auth}@{host}:{port}/{dbname}?sslmode={sslmode}"


def get_connection_params() -> dict:
    """
    Get PostgreSQL connection parameters as a dictionary.

    Returns:
        dict: Connection parameters for psycopg2/psycopg3
    """
    return {
        "host": settings.get("postgres.host", "localhost"),
        "port": settings.get("postgres.port", 5432),
        "user": settings.get("postgres.user", "postgres"),
        "password": settings.get("postgres.password", ""),
        "dbname": settings.get("postgres.dbname", "postgres"),
        "sslmode": settings.get("postgres.sslmode", "prefer"),
    }
