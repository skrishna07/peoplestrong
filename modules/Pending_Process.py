from libraries import *
from modules.Sql_Helper import *


def process_pending_queue():
    """Retries any records that failed in previous runs."""
    logging.info("[PHASE 1] Checking for stuck records in local queue...")
    conn = sqlite3.connect('erp_sync_queue.db')
    c = conn.cursor()
    c.execute("SELECT erpid, payload FROM pending_sync")
    rows = c.fetchall()
    conn.close()

    if rows:
        logging.info(f"[PHASE 1] Found {len(rows)} pending records. Attempting retry...")
        for erpid, payload_json in rows:
            payload = json.loads(payload_json)
            start_time = time.time()
            
               
    else:
        logging.info("[PHASE 1] Local queue is empty.")