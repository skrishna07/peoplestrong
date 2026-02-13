from libraries import *
import json
import sqlite3

DB_FILE = "erp_sync_queue1.db"

def init_db(db_conn=None):
    """Initializes the local queue to handle server downtime with payloads and progress tracking."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()
        c.execute('''
            CREATE TABLE IF NOT EXISTS pending_sync (
                candidate_id TEXT PRIMARY KEY,
                erpid TEXT,
                text_payload TEXT DEFAULT 'NA',
                file_payload TEXT DEFAULT 'NA',
                text_done BOOLEAN DEFAULT 0,
                file_done BOOLEAN DEFAULT 0,
                erp_done BOOLEAN DEFAULT 0,
                last_status TEXT,
                comments TEXT,
                timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        db_conn.commit()
        if own_conn:
            db_conn.close()
        logging.info("[DB] Persistence Layer Initialized.")
    except Exception as e:
        logging.error(f"[DB] Failed to initialize DB: {e}")


def save_to_queue(candidate_id, erpid=None, text_payload=None, file_payload=None,
                  text_done=None, file_done=None, erp_done=None, status=None, comments=None,
                  db_conn=None):
    """Save or update candidate progress including payloads in SQLite safely."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()

        # Convert payloads to JSON strings
        text_payload_str = json.dumps(text_payload) if text_payload is not None else 'NA'
        file_payload_str = json.dumps(file_payload) if file_payload is not None else 'NA'

        # UPSERT query with COALESCE for optional fields
        c.execute("""
            INSERT INTO pending_sync(candidate_id, erpid, text_payload, file_payload)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                erpid = COALESCE(?, erpid),
                text_payload = COALESCE(?, text_payload),
                file_payload = COALESCE(?, file_payload),
                text_done = COALESCE(?, text_done),
                file_done = COALESCE(?, file_done),
                erp_done = COALESCE(?, erp_done),
                last_status = COALESCE(?, last_status),
                comments = COALESCE(?, comments)
        """, (
            candidate_id, erpid, text_payload_str, file_payload_str,
            erpid, text_payload_str, file_payload_str,
            int(bool(text_done)) if text_done is not None else None,
            int(bool(file_done)) if file_done is not None else None,
            int(bool(erp_done)) if erp_done is not None else None,
            status,
            comments
        ))

        db_conn.commit()
        if own_conn:
            db_conn.close()
        logging.info(f"[DB] Candidate {candidate_id} saved to queue successfully.")
    except Exception as e:
        logging.error(f"[DB] Failed to save candidate {candidate_id} to queue: {e}")

def remove_from_queue(candidate_id, db_conn=None):
    """Remove a candidate from the pending queue after completion."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()
        c.execute("DELETE FROM pending_sync WHERE candidate_id = ?", (candidate_id,))
        db_conn.commit()
        if own_conn:
            db_conn.close()
    except Exception as e:
        logging.error(f"[DB] Failed to remove candidate {candidate_id} from queue: {e}")


def fetch_pending_candidates(db_conn=None):
    """Fetch all candidates that have not completed ERP push yet."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()
        c.execute("""
            SELECT candidate_id, erpid, text_payload, file_payload, text_done, file_done, erp_done, last_status, comments
            FROM pending_sync
            WHERE erp_done=0
        """)
        rows = c.fetchall()
        if own_conn:
            db_conn.close()
        return rows
    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates: {e}")
        return []
