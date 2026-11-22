import os
import psycopg
from psycopg.rows import dict_row


def get_connection():
    return psycopg.connect(
        host=os.getenv("DB_HOST", "127.0.0.1"),
        port=int(os.getenv("DB_PORT", "15432")),
        dbname=os.getenv("DB_NAME", "incident_db"),
        user=os.getenv("DB_USER", "aiops"),
        password=os.environ["AIOPS_DB_PASSWORD"],
        connect_timeout=5,
        row_factory=dict_row,
    )
