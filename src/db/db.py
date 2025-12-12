import sqlite3
import pandas as pd
from contextlib import contextmanager

class DatabaseConn:
    def __init__(self, db_path: str = "clutch_predict.db") -> None:
        self.db_path = db_path
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA synchronous=NORMAL")
        conn.execute("PRAGMA cache_size=10000")
        conn.execute("PRAGMA temp_store=MEMORY")
        conn.close()
    
    @contextmanager
    def get_connection(self):
        conn = sqlite3.connect(self.db_path)
        try:
            yield conn
        finally:
            conn.close()
    
    def insert_into_table(self, dataframe: pd.DataFrame, table: str) -> None:
        with self.get_connection() as conn:
            dataframe.to_sql(
                table, 
                conn, 
                if_exists='append', 
                index=False,
                method='multi',
                chunksize=1000
            )