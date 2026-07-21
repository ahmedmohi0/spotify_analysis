
from contextlib import contextmanager
import psycopg
from src.config import DB_CONFIG
from src.logger import get_logger, setup_logging
 
setup_logging()
logger = get_logger(__name__)
 
 
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
