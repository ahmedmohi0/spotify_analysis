from src.DB import run_sql_file
from src.logger import setup_logging, get_logger

setup_logging()
logger = get_logger(__name__)

if __name__ == "__main__":
    run_sql_file("sql/transform.sql")