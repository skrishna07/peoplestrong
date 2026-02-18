from libraries import *
import json
import sqlite3
import os
import logging

DB_FILE = "Production_erp_sync_queue.db"
FILE_DIR = "pending_files"
CSV_FILE = os.path.join(FILE_DIR, "pending_sync.csv")

os.makedirs(FILE_DIR, exist_ok=True)


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
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candidate_id TEXT UNIQUE NOT NULL,
                erpid TEXT,
                batch_date TEXT,
                mapping_file TEXT,
                source_file TEXT,
                text_payload TEXT,
                file_path TEXT,
                text_done INTEGER DEFAULT 0,
                file_done INTEGER DEFAULT 0,
                erp_done INTEGER DEFAULT 0,
                retry_count INTEGER DEFAULT 0,
                last_retry_at DATETIME,
                overall_status TEXT,
                erp_status TEXT,
                erp_response TEXT,
                error_message TEXT,
                failed_phase TEXT,
                comments TEXT,
                pull_status TEXT,
                pull_Error TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        # Optional indexes
        c.execute("CREATE INDEX IF NOT EXISTS idx_erp_done ON pending_sync (erp_done)")
        c.execute("CREATE INDEX IF NOT EXISTS idx_source_file ON pending_sync (source_file)")

        db_conn.commit()
        if own_conn:
            db_conn.close()
        logging.info("[DB] Persistence Layer Initialized.")
    except Exception as e:
        logging.error(f"[DB] Failed to initialize DB: {e}")


def save_base64_file(candidate_id, base64_data):
    """Save base64 file to disk and return the file path."""
    try:
        file_path = os.path.join(FILE_DIR, f"{candidate_id}.b64")
        with open(file_path, "w") as f:
            f.write(base64_data)
        return file_path
    except Exception as e:
        logging.error(f"[DB] Failed to save base64 file for {candidate_id}: {e}")
        return None


def save_to_queue(candidate_id, erpid, text_payload=None, file_path=None, db_conn=None,
                  batch_date=None, mapping_file=None, source_file=None,
                  text_done=None, file_done=None, erp_done=None,
                  overall_status=None, erp_status=None,
                  erp_response=None, error_message=None, failed_phase=None, comments=None):
    """Save candidate data to pending_sync table with safe UPSERT."""
    try:
        text_payload_str = json.dumps(text_payload) if isinstance(text_payload, dict) else text_payload

        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        cursor = db_conn.cursor()
        cursor.execute("""
            INSERT INTO pending_sync
            (candidate_id, erpid, batch_date, mapping_file, source_file,
             text_payload, file_path, text_done, file_done, erp_done,
             overall_status, erp_status, erp_response,
             error_message, failed_phase, comments)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(candidate_id) DO UPDATE SET
                erpid=COALESCE(excluded.erpid, pending_sync.erpid),
                batch_date=COALESCE(excluded.batch_date, pending_sync.batch_date),
                mapping_file=COALESCE(excluded.mapping_file, pending_sync.mapping_file),
                source_file=COALESCE(excluded.source_file, pending_sync.source_file),
                text_payload=COALESCE(excluded.text_payload, pending_sync.text_payload),
                file_path=COALESCE(excluded.file_path, pending_sync.file_path),
                text_done=COALESCE(excluded.text_done, pending_sync.text_done),
                file_done=COALESCE(excluded.file_done, pending_sync.file_done),
                erp_done=COALESCE(excluded.erp_done, pending_sync.erp_done),
                overall_status=COALESCE(excluded.overall_status, pending_sync.overall_status),
                erp_status=COALESCE(excluded.erp_status, pending_sync.erp_status),
                erp_response=COALESCE(excluded.erp_response, pending_sync.erp_response),
                error_message=COALESCE(excluded.error_message, pending_sync.error_message),
                failed_phase=COALESCE(excluded.failed_phase, pending_sync.failed_phase),
                comments=COALESCE(excluded.comments, pending_sync.comments),
                updated_at=CURRENT_TIMESTAMP
        """, (candidate_id, erpid, batch_date, mapping_file, source_file,
              text_payload_str, file_path, text_done, file_done, erp_done,
              overall_status, erp_status, erp_response,
              error_message, failed_phase, comments))
        db_conn.commit()
        update_csv(candidate_id, erpid, batch_date, mapping_file, source_file,
                   text_payload, file_path, text_done, file_done, erp_done,
                   overall_status, erp_status, erp_response, error_message,
                   failed_phase, comments)
        if own_conn:
            db_conn.close()
        logging.info(f"[DB] Candidate {candidate_id} saved/updated in queue successfully.")
    except Exception as e:
        logging.error(f"[DB] Failed to save candidate {candidate_id} to queue: {e}")


def remove_from_queue(candidate_id, db_conn=None):
    """Remove a candidate from the pending queue after completion and delete file."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        # Delete file if exists
        c = db_conn.cursor()
        c.execute("SELECT file_path FROM pending_sync WHERE candidate_id = ?", (candidate_id,))
        row = c.fetchone()
        if row and row[0] not in (None, 'NA') and os.path.exists(row[0]):
            os.remove(row[0])

        # Delete DB record
        c.execute("DELETE FROM pending_sync WHERE candidate_id = ?", (candidate_id,))
        db_conn.commit()
        if own_conn:
            db_conn.close()
        logging.info(f"[DB] Candidate {candidate_id} removed from queue successfully.")
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
            SELECT candidate_id, erpid,batch_date, text_payload, file_path, text_done, file_done, erp_done,
                   overall_status, comments, source_file, mapping_file
            FROM pending_sync
            WHERE erp_done=0
            ORDER BY created_at ASC
        """)
        rows = c.fetchall()
        if own_conn:
            db_conn.close()
        return rows
    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates: {e}")
        return []




def update_pull_status(candidate_id, status, error_msg=None, db_conn=None):
    """
    Update the pull_status and pull_Error fields for a candidate in pending_sync.
    
    status: "SUCCESS" or "FAILED"
    error_msg: optional error message if failed
    """
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        cursor = db_conn.cursor()
        cursor.execute("""
            UPDATE pending_sync
            SET pull_status = ?,
                pull_Error = ?,
                updated_at = CURRENT_TIMESTAMP
            WHERE candidate_id = ?
        """, (status, error_msg, candidate_id))
        db_conn.commit()
        if own_conn:
            db_conn.close()
        logging.info(f"[PULL] Candidate {candidate_id} pull status updated: {status}")
    except Exception as e:
        logging.error(f"[PULL] Failed to update pull status for {candidate_id}: {e}")





import csv

CSV_FILE = os.path.join(FILE_DIR, "pending_sync.csv")

def update_csv(candidate_id, erpid, batch_date=None, mapping_file=None, source_file=None,
               text_payload=None, file_path=None, text_done=None, file_done=None, erp_done=None,
               overall_status=None, erp_status=None, erp_response=None, error_message=None,
               failed_phase=None, comments=None):
    """Append or update candidate info in CSV."""
    text_payload_str = json.dumps(text_payload) if isinstance(text_payload, dict) else text_payload
    fieldnames = ['candidate_id', 'erpid', 'batch_date', 'mapping_file', 'source_file',
                  'text_payload', 'file_path', 'text_done', 'file_done', 'erp_done',
                  'overall_status', 'erp_status', 'erp_response', 'error_message',
                  'failed_phase', 'comments']

    rows = []
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            rows = list(reader)

    updated = False
    for row in rows:
        if row['candidate_id'] == candidate_id:
            row.update({
                'erpid': erpid, 'batch_date': batch_date, 'mapping_file': mapping_file,
                'source_file': source_file, 'text_payload': text_payload_str,
                'file_path': file_path, 'text_done': text_done, 'file_done': file_done,
                'erp_done': erp_done, 'overall_status': overall_status, 'erp_status': erp_status,
                'erp_response': erp_response, 'error_message': error_message,
                'failed_phase': failed_phase, 'comments': comments
            })
            updated = True
            break

    if not updated:
        rows.append({
            'candidate_id': candidate_id, 'erpid': erpid, 'batch_date': batch_date, 'mapping_file': mapping_file,
            'source_file': source_file, 'text_payload': text_payload_str,
            'file_path': file_path, 'text_done': text_done, 'file_done': file_done,
            'erp_done': erp_done, 'overall_status': overall_status, 'erp_status': erp_status,
            'erp_response': erp_response, 'error_message': error_message,
            'failed_phase': failed_phase, 'comments': comments
        })

    with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)







def fetch_pull_pending_candidates(db_conn=None):
    """Fetch all candidates that have pull_status PENDING or FAILED."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()
        c.execute("""
            SELECT candidate_id, erpid, batch_date, text_payload, file_path, text_done, file_done, erp_done,
                   overall_status, comments, source_file, mapping_file, pull_status, pull_Error
            FROM pending_sync
            WHERE pull_status IN ('PENDING', 'FAILED')
            ORDER BY created_at ASC
        """)
        rows = c.fetchall()
        if own_conn:
            db_conn.close()
        return rows
    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates by pull_status: {e}")
        return []
