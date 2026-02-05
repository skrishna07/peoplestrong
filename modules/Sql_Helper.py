
from libraries import *

def init_db():
    """Initializes the local queue to handle server downtime."""
    try:
        conn = sqlite3.connect('erp_sync_queue.db')
        c = conn.cursor()
        c.execute('''CREATE TABLE IF NOT EXISTS pending_sync 
                     (erpid TEXT PRIMARY KEY, payload TEXT, timestamp DATETIME DEFAULT CURRENT_TIMESTAMP)''')
        conn.commit()
        conn.close()
        logging.info("[DB] SQLite Persistence Layer Initialized.")
    except Exception as e:
        logging.error(f"[DB] Failed to initialize SQLite: {e}")

def save_to_queue(erpid, payload):
    conn = sqlite3.connect('erp_sync_queue.db')
    c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO pending_sync (erpid, payload) VALUES (?, ?)", (erpid, json.dumps(payload)))
    conn.commit()
    conn.close()

def remove_from_queue(erpid):
    conn = sqlite3.connect('erp_sync_queue.db')
    c = conn.cursor()
    c.execute("DELETE FROM pending_sync WHERE erpid = ?", (erpid,))
    conn.commit()
    conn.close()

