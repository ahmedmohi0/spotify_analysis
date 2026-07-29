
from contextlib import contextmanager
import psycopg
from src.config import DB_CONFIG
from src.logger import get_logger, setup_logging
from sqlalchemy import URL,create_engine,text
import pandas as pd
setup_logging()
logger = get_logger(__name__)
 
_engine = None
@contextmanager
def get_connection():
    """
    Context-managed Postgres connection. Commits on success,
    rolls back and re-raises on any exception.
    """
    conn = psycopg.connect(**DB_CONFIG)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Transaction rolled back due to an error.")
        raise
    finally:
        conn.close()

def run_sql_file(filepath: str) -> None:
    """
    Executes a .sql file against the database in a single transaction.
    Used for schema.sql and the transform.sql layer.
    """
    logger.info(f"Running SQL file: {filepath}")
    with open(filepath, "r") as f:
        sql_text = f.read()
 
    with get_connection() as conn:
        with conn.cursor() as cur:
            cur.execute(sql_text)
 
    logger.info(f"Finished running: {filepath}")

def run_schema(schema_path: str = "schema.sql") -> None:
    """
    Convenience wrapper for (re)building the schema from scratch.
    """
    run_sql_file(schema_path)


def bulk_insert(table: str, columns: list[str], rows: list[tuple]) -> None:
    """
    Bulk-inserts rows into `table` using psycopg3's native COPY protocol.
    This is the fastest bulk-load path in psycopg3 — no execute_values
    equivalent needed, COPY is built into the cursor API directly.
    """
    if not rows:
        logger.warning(f"bulk_insert called with no rows for table: {table}")
        return
 
    col_list = ", ".join(columns)
    copy_sql = f"COPY {table} ({col_list}) FROM STDIN"
 
    with get_connection() as conn:
        with conn.cursor() as cur:
            with cur.copy(copy_sql) as copy:
                for row in rows:
                    copy.write_row(row)
 
    logger.info(f"Inserted {len(rows)} rows into {table} via COPY.")


def get_engine():
    global _engine
    if _engine is None:
        logger.debug("No engine found - creating new one")
        required = ["host", "port", "dbname", "user", "password"]
        missing = [k for k in required if k not in DB_CONFIG]
        if missing:
            logger.critical(f"missing config keys: {missing}")
            raise EnvironmentError(f"missing config keys: {missing}")

        url = URL.create(
            drivername="postgresql+psycopg",
            username=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            database=DB_CONFIG["dbname"],
        )
        try:
            _engine = create_engine(url, echo=False)
            logger.info("Database engine initialized")
        except Exception as e:
            logger.critical(f"failed to create database engine: {e}")
            raise
    else:
        logger.debug("using existing engine")

    return _engine


def query(sql: str, params: dict = None) -> pd.DataFrame:
    logger.debug(f"Executing query: {sql[:120].strip()}{'...' if len(sql) > 120 else ''}")
    try:
        engine = get_engine()
        with engine.connect() as conn:
            result = conn.execute(text(sql), params or {})
            df = pd.DataFrame(result.fetchall(), columns=result.keys())
        if df.empty:
            logger.warning("Query returned 0 rows — verify filters are correct.")
        else:
            logger.debug(f"Query returned {len(df):,} rows.")
        return df
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise


def query_table(table_name: str) -> pd.DataFrame:
    return pd.read_sql_table(table_name, con=get_engine())