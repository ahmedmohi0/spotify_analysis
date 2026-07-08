
from contextlib import contextmanager
import psycopg
from config import DB_CONFIG
from logger import get_logger
 
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
 