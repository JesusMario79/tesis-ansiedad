# test_mysql.py
import os
import pymysql
from dotenv import load_dotenv

load_dotenv()  # lee tu .env

cfg = {k: os.getenv(k) for k in ["DB_HOST","DB_PORT","DB_USER","DB_PASSWORD","DB_NAME"]}
print("Intentando conectar con:", cfg)

conn = pymysql.connect(
    host=cfg["DB_HOST"],
    port=int(cfg["DB_PORT"]),
    user=cfg["DB_USER"],
    password=cfg["DB_PASSWORD"],
    database=cfg["DB_NAME"],
    charset="utf8mb4",
    cursorclass=pymysql.cursors.DictCursor,
)

with conn.cursor() as cur:
    cur.execute("SELECT 1 AS ok")
    print("Conexión OK →", cur.fetchone())

conn.close()
