import sqlite3

DB_NAME = "checklist.db"

def get_connection():
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def init_db():
    conn = get_connection()
    cur = conn.cursor()

    # Usuarios
    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        username TEXT UNIQUE,
        password TEXT,
        rol TEXT
    )
    """)

    # Checklist maestro
    cur.execute("""
    CREATE TABLE IF NOT EXISTS checklist_items (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        categoria TEXT,
        item TEXT,
        puntaje_max INTEGER
    )
    """)

    # Resultados
    cur.execute("""
    CREATE TABLE IF NOT EXISTS checklist_results (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        fecha TEXT,
        area TEXT,
        usuario TEXT,
        categoria TEXT,
        item TEXT,
        puntaje INTEGER,
        observacion TEXT
    )
    """)

    conn.commit()
    conn.close()
