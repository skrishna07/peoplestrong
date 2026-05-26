from libraries import *
import json
import sqlite3
import os
import logging

DB_FILE = "Production_erp_sync_queue1.db"
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

        # Add dropped tracking columns if they don't exist
        try:
            c.execute("ALTER TABLE pending_sync ADD COLUMN lifecycle_status TEXT DEFAULT 'Processing'")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            c.execute("ALTER TABLE pending_sync ADD COLUMN dropped_at DATETIME")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            c.execute("ALTER TABLE pending_sync ADD COLUMN drop_reason TEXT")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            c.execute("ALTER TABLE pending_sync ADD COLUMN pull_retry_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists
        try:
            c.execute("ALTER TABLE pending_sync ADD COLUMN pull_retry_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # Column already exists

        db_conn.commit()
        if own_conn:
            db_conn.close()
        logging.info("[DB] Persistence Layer Initialized.")
    except Exception as e:
        logging.error(f"[DB] Failed to initialize DB: {e}")


def _to_int_flag(value, default=0):
    try:
        if value in (None, "", "None"):
            return default
        return int(float(str(value).strip()))
    except Exception:
        return default


def _empty_to_none(value):
    if value is None:
        return None
    val = str(value).strip()
    return val if val else None


def sync_queue_from_csv(db_conn=None, csv_path=CSV_FILE, filter_criteria=None, limit=None):
    """Backfill missing pending records from CSV into SQLite queue with optional filtering and limiting."""
    try:
        if not os.path.exists(csv_path):
            logging.info(f"[DB SYNC] CSV not found, skipping sync: {csv_path}")
            return 0

        own_conn = False
        if db_conn is None:
            try:
                db_conn = sqlite3.connect(DB_FILE)
                own_conn = True
            except sqlite3.Error as db_err:
                logging.error(f"[DB SYNC] Failed to connect to database: {db_err}")
                return 0

        cursor = db_conn.cursor()
        cursor.execute("SELECT candidate_id FROM pending_sync")
        existing_ids = {row[0] for row in cursor.fetchall() if row and row[0]}

        try:
            with open(csv_path, newline='', encoding='utf-8') as f:
                rows = list(csv.DictReader(f))
        except Exception as file_err:
            logging.error(f"[DB SYNC] Failed to read CSV file: {file_err}")
            return 0

        # Apply filtering criteria if provided
        if filter_criteria:
            rows = [row for row in rows if filter_criteria(row)]

        # Apply limit if provided
        if limit:
            rows = rows[:limit]

        inserted = 0
        for row in rows:
            candidate_id = _empty_to_none(row.get("candidate_id"))
            if not candidate_id or candidate_id in existing_ids:
                continue

            try:
                cursor.execute("""
                    INSERT INTO pending_sync
                    (candidate_id, erpid, batch_date, mapping_file, source_file,
                     text_payload, file_path, text_done, file_done, erp_done,
                     overall_status, erp_status, erp_response,
                     error_message, failed_phase, comments)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    candidate_id,
                    _empty_to_none(row.get("erpid")) or candidate_id,
                    _empty_to_none(row.get("batch_date")),
                    _empty_to_none(row.get("mapping_file")),
                    _empty_to_none(row.get("source_file")),
                    _empty_to_none(row.get("text_payload")),
                    _empty_to_none(row.get("file_path")),
                    _to_int_flag(row.get("text_done"), default=0),
                    _to_int_flag(row.get("file_done"), default=0),
                    _to_int_flag(row.get("erp_done"), default=0),
                    _empty_to_none(row.get("overall_status")) or "PENDING",
                    _empty_to_none(row.get("erp_status")),
                    _empty_to_none(row.get("erp_response")),
                    _empty_to_none(row.get("error_message")),
                    _empty_to_none(row.get("failed_phase")),
                    _empty_to_none(row.get("comments"))
                ))
                inserted += 1
            except sqlite3.Error as insert_err:
                logging.error(f"[DB SYNC] Failed to insert row for candidate {candidate_id}: {insert_err}")

        db_conn.commit()

        if own_conn:
            db_conn.close()

        logging.info(f"[DB SYNC] CSV→DB sync complete. Added {inserted} missing candidate(s).")
        return inserted

    except Exception as e:
        logging.error(f"[DB SYNC] Unexpected error during sync: {e}")
        return 0


def check_and_drop_expired_candidates(sftp, db_conn=None, expiry_days=30):
    """
    Mark candidates as Dropped if their batch_date is older than expiry_days.
    Write dropped candidate details to Dropped_ID/dropped_ids.csv on SFTP.
    Only candidates with lifecycle_status != 'Dropped' are eligible.
    """
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        cursor = db_conn.cursor()
        today = datetime.now().date()
        cutoff_date = today - pd.Timedelta(days=expiry_days)

        # Find candidates within expiry window but not yet dropped
        cursor.execute("""
            SELECT candidate_id, erpid, batch_date, mapping_file, created_at,
                   overall_status, comments
            FROM pending_sync
            WHERE batch_date IS NOT NULL
              AND lifecycle_status != 'Dropped'
              AND CAST(batch_date AS DATE) < ?
              AND IFNULL(erp_done, 0) = 0
            ORDER BY batch_date ASC
        """, (str(cutoff_date),))
        
        expired = cursor.fetchall()
        if not expired:
            logging.info("[EXPIRY] No candidates expired in this run.")
            if own_conn:
                db_conn.close()
            return 0

        logging.info(f"[EXPIRY] Found {len(expired)} candidate(s) to DROP (> {expiry_days} days old).")

        # Update DB: mark as Dropped
        for cid, erpid, batch_date, mapping_file, created_at, overall_status, comments in expired:
            drop_reason = f"Batch date {batch_date} is older than {expiry_days} days (cutoff: {cutoff_date}). Previous status: {overall_status}"
            cursor.execute("""
                UPDATE pending_sync
                SET lifecycle_status = 'Dropped',
                    dropped_at = CURRENT_TIMESTAMP,
                    drop_reason = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE candidate_id = ?
            """, (drop_reason, cid))

        db_conn.commit()

        # Build dropped CSV row data
        dropped_rows = []
        for cid, erpid, batch_date, mapping_file, created_at, overall_status, comments in expired:
            drop_reason = f"Batch date {batch_date} is older than {expiry_days} days (cutoff: {cutoff_date}). Previous status: {overall_status}"
            dropped_rows.append({
                "candidate_id": cid,
                "erpid": erpid or "N/A",
                "batch_date": batch_date or "N/A",
                "mapping_file": mapping_file or "N/A",
                "created_date": created_at or "N/A",
                "processed_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "last_modified_date": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "drop_reason": drop_reason,
                "status": "Dropped"
            })

        # Write to SFTP Dropped_ID folder
        if dropped_rows:
            try:
                outbound_root = ARCHIVE_DIR.rsplit("/", 1)[0] if "/" in ARCHIVE_DIR else ARCHIVE_DIR
                dropped_dir = f"{outbound_root}/Dropped_ID"
                
                # Create folder if needed
                try:
                    sftp.stat(dropped_dir)
                except IOError:
                    sftp.mkdir(dropped_dir)

                # Read existing dropped IDs CSV if it exists
                dropped_csv_path = f"{dropped_dir}/dropped_ids.csv"
                existing_rows = []
                try:
                    with sftp.open(dropped_csv_path, "rb") as f:
                        existing_data = f.read().decode('utf-8')
                        if existing_data:
                            reader = list(csv.DictReader(io.StringIO(existing_data)))
                            existing_rows = reader
                except IOError:
                    pass

                # Merge with new dropped rows (avoid duplicates)
                existing_ids = {row.get("candidate_id") for row in existing_rows}
                merged_rows = existing_rows + [r for r in dropped_rows if r["candidate_id"] not in existing_ids]

                # Write merged CSV to SFTP
                if merged_rows:
                    fieldnames = ["candidate_id", "erpid", "batch_date", "mapping_file", 
                                 "created_date", "processed_date", "last_modified_date",
                                 "drop_reason", "status"]
                    csv_buffer = io.StringIO()
                    writer = csv.DictWriter(csv_buffer, fieldnames=fieldnames)
                    writer.writeheader()
                    writer.writerows(merged_rows)

                    with sftp.open(dropped_csv_path, "w") as f:
                        f.write(csv_buffer.getvalue())

                logging.info(f"[EXPIRY] Dropped IDs written to {dropped_csv_path} ({len(dropped_rows)} new)")

            except Exception as e:
                logging.error(f"[EXPIRY] Failed to write dropped IDs to SFTP: {e}")

        if own_conn:
            db_conn.close()

        return len(expired)

    except Exception as e:
        logging.error(f"[EXPIRY] check_and_drop_expired_candidates failed: {e}")
        return 0


def backfill_batch_info_from_sftp(sftp, db_conn=None):
    """
    For pending candidates with NULL batch_date/source_file, scan all archived
    Mapping files on SFTP to find which batch each candidate belongs to,
    then update DB with batch_date + source_file so rebuild_payload_from_batch() can work.
    """
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        cursor = db_conn.cursor()
        cursor.execute("""
            SELECT candidate_id FROM pending_sync
            WHERE batch_date IS NULL AND IFNULL(erp_done, 0) = 0
        """)
        pending_ids = {str(row[0]).strip() for row in cursor.fetchall() if row and row[0]}

        if not pending_ids:
            logging.info("[BACKFILL] All pending candidates already have batch_date. Nothing to backfill.")
            if own_conn:
                db_conn.close()
            return 0

        logging.info(f"[BACKFILL] {len(pending_ids)} candidates need batch/source backfill.")

        required_prefixes = [
            "CandidateData",
            "CandidateContact",
            "CandidateEducation",
            "CandidateEmergencyContact",
            "CandidateIDDetails",
            "CandidateSalaryData"
        ]
        start_mapping_date = datetime.strptime("13022026", "%d%m%Y").date()
        outbound_root = ARCHIVE_DIR.rsplit("/", 1)[0] if "/" in ARCHIVE_DIR else ARCHIVE_DIR
        master_dir = f"{outbound_root}/Master_Data"

        try:
            sftp.stat(master_dir)
        except Exception:
            sftp.mkdir(master_dir)
            logging.info(f"[MASTER_DATA] Created folder on SFTP: {master_dir}")

        try:
            archive_files = set(sftp.listdir(ARCHIVE_DIR))
        except Exception:
            archive_files = set()
        try:
            import_files = set(sftp.listdir(IMPORT_DIR))
        except Exception:
            import_files = set()
        all_files = archive_files | import_files

        mapping_pattern = re.compile(r"Mapping_(\d{8})_(\d{6})\.csv")
        mappings = []
        for f in all_files:
            m = mapping_pattern.match(f)
            if not m:
                continue
            map_date = datetime.strptime(m.group(1), "%d%m%Y").date()
            if map_date >= start_mapping_date:
                mappings.append((map_date, f))

        mappings.sort(key=lambda x: x[0])
        logging.info(f"[MASTER_DATA] Mapping files from {start_mapping_date}: {len(mappings)}")

        def _pick_latest(prefix, date_str):
            pat = re.compile(rf"{prefix}_{date_str}_(\d{{6}})\.csv")
            candidates = [name for name in all_files if pat.match(name)]
            if not candidates:
                return None
            candidates.sort(reverse=True)
            return candidates[0]

        master_rows = []
        candidate_to_batch = {}
        remaining = set(pending_ids)

        for mapping_date, mapping_file in mappings:
            map_dir = ARCHIVE_DIR if mapping_file in archive_files else IMPORT_DIR
            mapping_path = f"{map_dir}/{mapping_file}"

            # Business rule: mapping of day D drives candidate files of day D+1
            process_date = mapping_date + pd.Timedelta(days=1)
            process_date_str = process_date.strftime("%d%m%Y")
            fallback_same_day_str = mapping_date.strftime("%d%m%Y")

            source_files = []
            for prefix in required_prefixes:
                chosen = _pick_latest(prefix, process_date_str) or _pick_latest(prefix, fallback_same_day_str)
                if chosen:
                    source_files.append(chosen)

            try:
                with sftp.open(mapping_path, "rb") as fh:
                    df = pd.read_csv(io.BytesIO(fh.read()), sep="|", dtype=str)
                df.columns = df.columns.str.strip()
            except Exception as e:
                logging.warning(f"[MASTER_DATA] Unable to read {mapping_file}: {e}")
                continue

            people_col = "PeopleStrongID" if "PeopleStrongID" in df.columns else None
            erp_col = "ERPID" if "ERPID" in df.columns else None
            if not people_col and not erp_col:
                logging.warning(f"[MASTER_DATA] {mapping_file} missing both PeopleStrongID and ERPID")
                continue

            for _, row in df.iterrows():
                people_id = str(row.get(people_col, "")).strip() if people_col else ""
                erp_id = str(row.get(erp_col, "")).strip() if erp_col else ""
                candidate_id = people_id if people_id.startswith("PH") else (erp_id if erp_id.startswith("PH") else "")
                if not candidate_id:
                    continue

                source_file_json = json.dumps(source_files)
                master_rows.append({
                    "candidate_id": candidate_id,
                    "peopleStrong_id": people_id,
                    "erp_id": erp_id,
                    "mapping_file": mapping_file,
                    "mapping_date": mapping_date.strftime("%Y-%m-%d"),
                    "batch_date": process_date.strftime("%Y-%m-%d"),
                    "candidate_source_files": source_file_json,
                    "candidate_source_file_count": len(source_files)
                })

                if candidate_id in remaining and candidate_id not in candidate_to_batch and len(source_files) == 6:
                    candidate_to_batch[candidate_id] = (process_date.strftime("%Y-%m-%d"), source_files, mapping_file)
                    remaining.discard(candidate_id)

        # Persist master index on SFTP for operational visibility
        if master_rows:
            master_df = pd.DataFrame(master_rows)
            csv_buffer = io.StringIO()
            master_df.to_csv(csv_buffer, index=False)
            with sftp.open(f"{master_dir}/master_index.csv", "w") as mf:
                mf.write(csv_buffer.getvalue())
            logging.info(f"[MASTER_DATA] Uploaded master index with {len(master_rows)} row(s) to {master_dir}/master_index.csv")

        # Update DB from resolved mapping->batch links
        updated = 0
        for cid, (batch_date_val, src_files, mapping_file) in candidate_to_batch.items():
            cursor.execute("""
                UPDATE pending_sync
                SET batch_date = ?, source_file = ?, mapping_file = ?, updated_at = CURRENT_TIMESTAMP
                WHERE candidate_id = ? AND batch_date IS NULL
            """, (batch_date_val, json.dumps(src_files), mapping_file, cid))
            updated += 1

        db_conn.commit()
        logging.info(
            f"[BACKFILL] batch_date/source_file updated for {updated} candidate(s). "
            f"{len(remaining)} pending candidate(s) still unmatched or missing required 6 files."
        )

        if own_conn:
            db_conn.close()
        return updated

    except Exception as e:
        logging.error(f"[BACKFILL] backfill_batch_info_from_sftp failed: {e}")
        return 0


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


# def fetch_pending_candidates(db_conn=None):
#     """Fetch all candidates that have not completed ERP push yet."""
#     try:
#         own_conn = False
#         if db_conn is None:
#             db_conn = sqlite3.connect(DB_FILE)
#             own_conn = True

#         c = db_conn.cursor()
#         c.execute("""
#             SELECT candidate_id, erpid,batch_date, text_payload, file_path, text_done, file_done, erp_done,
#                    overall_status, comments, source_file, mapping_file
#             FROM pending_sync
#             WHERE erp_done=0
#             ORDER BY created_at ASC
#         """)
#         rows = c.fetchall()
#         if own_conn:
#             db_conn.close()
#         return rows
#     except Exception as e:
#         logging.error(f"[DB] Failed to fetch pending candidates: {e}")
#         return []


def fetch_pending_candidates(db_conn=None):
    """Fetch all candidates that are not fully synced (text/file/ERP) and not dropped."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()
        c.execute("""
            SELECT candidate_id,
                   erpid,
                   batch_date,
                   text_payload,
                   file_path,
                   IFNULL(text_done, 0) AS text_done,
                   IFNULL(file_done, 0) AS file_done,
                   IFNULL(erp_done, 0) AS erp_done,
                   overall_status,
                   comments,
                   source_file,
                   mapping_file
            FROM pending_sync
            WHERE (IFNULL(erp_done, 0) = 0
               OR IFNULL(text_done, 0) = 0
               OR IFNULL(file_done, 0) = 0)
                            AND IFNULL(overall_status, '') != 'SUCCESS'
              AND (lifecycle_status IS NULL OR lifecycle_status != 'Dropped')
            ORDER BY created_at ASC
        """)

        rows = c.fetchall()

        if own_conn:
            db_conn.close()

        return rows

    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates: {e}")
        return []




def fetch_recent_pending_candidates(db_conn=None, recent_ids=None):
    """Fetch pending candidates from DB, optionally filtered by recent IDs."""
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()

        query = """
            SELECT candidate_id,
                   erpid,
                   batch_date,
                   text_payload,
                   file_path,
                   IFNULL(text_done, 0) AS text_done,
                   IFNULL(file_done, 0) AS file_done,
                   IFNULL(erp_done, 0) AS erp_done,
                   overall_status,
                   comments,
                   source_file,
                   mapping_file
            FROM pending_sync
            WHERE (IFNULL(erp_done, 0) = 0
               OR IFNULL(text_done, 0) = 0
               OR IFNULL(file_done, 0) = 0)
                            AND IFNULL(overall_status, '') != 'SUCCESS'
              AND (lifecycle_status IS NULL OR lifecycle_status != 'Dropped')
        """

        params = ()
        if recent_ids:
            placeholders = ",".join("?" for _ in recent_ids)
            query += f" AND candidate_id IN ({placeholders})"
            params = tuple(recent_ids)

        query += " ORDER BY created_at ASC"

        c.execute(query, params)
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
        # Increment retry count only when marking back to PENDING (avoids count growing on SUCCESS/SKIPPED)
        if status == "PENDING":
            cursor.execute("""
                UPDATE pending_sync
                SET pull_status = ?,
                    pull_Error = ?,
                    pull_retry_count = COALESCE(pull_retry_count, 0) + 1,
                    updated_at = CURRENT_TIMESTAMP
                WHERE candidate_id = ?
                   OR erpid = ?
            """, (status, error_msg, candidate_id, candidate_id))
        else:
            cursor.execute("""
                UPDATE pending_sync
                SET pull_status = ?,
                    pull_Error = ?,
                    updated_at = CURRENT_TIMESTAMP
                WHERE candidate_id = ?
                   OR erpid = ?
            """, (status, error_msg, candidate_id, candidate_id))
        updated_rows = cursor.rowcount
        db_conn.commit()
        if own_conn:
            db_conn.close()
        if updated_rows == 0:
            logging.warning(f"[PULL] No pending_sync row matched for identifier {candidate_id}; status not updated.")
        else:
            logging.info(f"[PULL] Candidate {candidate_id} pull status updated: {status} (rows: {updated_rows})")
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
    """Fetch candidates that still need pull processing.

    Includes:
    - explicit pull_status PENDING/FAILED
    - legacy rows where overall_status is PENDING but pull_status is NULL/blank
    """
    try:
        own_conn = False
        if db_conn is None:
            db_conn = sqlite3.connect(DB_FILE)
            own_conn = True

        c = db_conn.cursor()
        # Skip IDs retried 15+ times with no success — they are persistently invalid
        # and will be skipped until manually reset (set pull_retry_count = 0).
        c.execute("""
            SELECT candidate_id, erpid, batch_date, text_payload, file_path, text_done, file_done, erp_done,
                   overall_status, comments, source_file, mapping_file, pull_status, pull_Error
            FROM pending_sync
            WHERE COALESCE(pull_retry_count, 0) < 15
              AND (
                    pull_status IN ('PENDING', 'FAILED')
                    OR (
                          COALESCE(TRIM(pull_status), '') = ''
                          AND COALESCE(UPPER(TRIM(overall_status)), '') = 'PENDING'
                       )
                  )
            ORDER BY created_at ASC
        """)
        rows = c.fetchall()
        if own_conn:
            db_conn.close()
        return rows
    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates by pull_status: {e}")
        return []
