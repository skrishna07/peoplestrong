# ============================================================
# PEOPLESTRONG → ERP |
# ============================================================

from libraries import *
from modules.Helpers import *
from modules.Text_Field_Validator import *
from modules.Files_Field_Validator import *
from modules.Sql_Helper import *
from modules.Pending_Process import *
from modules.Csv_File_Handler import *
from api_handler.Ps_to_Erp_Requestor import send_to_erp,is_erp_id_valid
from modules.Document_Base64_Generator import get_candidate_document_links
from modules.SEND_EMAIL_SUMMARY import send_push_summary_email, send_mapping_alert_email, send_smtp_email,send_erp_error_summary,send_no_data_alert
from modules.Pending_Process import Push_Pending
from modules.ERP_Builder import build_erp_payload
from modules.Yes_No_Validator import ensure_tracking_files, should_skip_push, update_push_tracking, get_push_tracking_row
from concurrent.futures import ThreadPoolExecutor

REPORT_FILE = "PeopleStrong_Master_Report.xlsx"


# =================== Helper Functions =====================

def archive_batch_files(sftp, files, move_file=True, source_lookup=None):
    source_lookup = source_lookup or {}
    for f_name in files:
        try:
            source_dir = source_lookup.get(f_name, IMPORT_DIR)
            source_path = f"{source_dir}/{f_name}"
            if source_dir == ARCHIVE_DIR:
                logging.info("[ARCHIVE] File already in archive, skipping move/copy: %s", f_name)
                continue
            safe_archive_file(sftp, source_path, ARCHIVE_DIR, move_file=move_file)
            logging.info("[ARCHIVE] %s: %s", "Moved" if move_file else "Copied", f_name)
        except Exception as e:
            logging.error("[ARCHIVE ERROR] %s", str(e))


def record_pending_ids(db_conn, candidate_ids, reason="No candidate data found — pending for future processing"):
    for cid in candidate_ids:
        save_to_queue(
            candidate_id=cid,
            erpid=cid,
            overall_status=STATUS_PENDING,
            comments=reason,
            db_conn=db_conn
        )








# =================== Main Function ========================

def PS_to_ERP_Push(db_conn=None, max_ids=None):
    logging.info("===== PEOPLESTRONG → ERP START =====")
    logging.info(f"Job Started At: {datetime.now()}")

    # ------------------- Phase 1: Initialize DB -------------------
    own_conn = False
    if db_conn is None:
        import sqlite3 as _sqlite3
        db_conn = _sqlite3.connect("Production_erp_sync_queue1.db", check_same_thread=False)
        own_conn = True

    try:
        init_db(db_conn=db_conn)
        sync_queue_from_csv(db_conn=db_conn)
        ensure_tracking_files()
    except Exception as e:
        logging.error("[DB] Database initialization failed: %s", str(e))
        print("Database Not Initialized")

    # ------------------- Phase 2: Connect SFTP -------------------
    try:
        ssh, sftp = get_sftp_connection()
        logging.info("[PHASE 2] SFTP connected")
    except Exception as e:
        logging.error("[SFTP] Connection failed: %s", str(e))
        return

    try:
        sync_data_master_to_sftp_debugging(sftp)
        logging.info("[DEBUGGING] Initial data_master sync completed")
    except Exception as e:
        logging.error(f"[DEBUGGING] Initial data_master sync failed: {e}")

    # ------------------- Backfill batch info for old pending candidates -------------------
    try:
        backfilled = backfill_batch_info_from_sftp(sftp=sftp, db_conn=db_conn)
        if backfilled:
            logging.info(f"[BACKFILL] Resolved batch info for {backfilled} previously unlinked candidate(s).")
    except Exception as e:
        logging.error(f"[BACKFILL] Batch info backfill failed: {e}")

    # ------------------- Check for expired candidates (>30 days) and drop them -------------------
    try:
        from modules.Sql_Helper import check_and_drop_expired_candidates
        dropped = check_and_drop_expired_candidates(sftp=sftp, db_conn=db_conn, expiry_days=30)
        if dropped:
            logging.info(f"[EXPIRY] Marked {dropped} candidate(s) as Dropped (>30 days old).")
    except Exception as e:
        logging.error(f"[EXPIRY] Expiry check failed: {e}")

    try:
        Push_Pending(db_conn=db_conn, max_ids=max_ids)
    except Exception as e:
        logging.error(f"[PENDING] Failed to process pending queue: {e}")

    # ------------------- Phase 3: Load CSVs -------------------
    logging.info("[PHASE 3] Loading CSVs...")
    try:
        dfs, batch_date, mapping_file, source_file = load_csvs(sftp)
        source_lookup = getattr(load_csvs, "source_lookup", {})
        mapping_df = dfs.get("Mapping")
    except Exception as e:
        logging.error("[CSV] Failed to load CSVs: %s", str(e))
        ssh.close()
        return

    # ------------------- Phase 4: Validate Mapping -------------------
    if mapping_df is None or mapping_df.empty:
        logging.warning("[ALERT] Mapping CSV is empty or missing candidate IDs. Automation stopped.")
        send_mapping_alert_email(mapping_file_name=str(mapping_file), missing_ids=None)
        logging.info("[ARCHIVE] Archiving invalid mapping batch...")
        archive_batch_files(sftp, source_file, move_file=True, source_lookup=source_lookup)
        sftp.close()
        ssh.close()
        return

    mapping_df[JOIN_KEY] = mapping_df[JOIN_KEY].astype(str).str.strip()
    batch_date_value = batch_date.isoformat() if hasattr(batch_date, "isoformat") else str(batch_date or "")

    missing_ids = mapping_df[mapping_df[JOIN_KEY].isna()][JOIN_KEY].tolist()
    if missing_ids:
        logging.warning(f"[ALERT] {len(missing_ids)} candidate IDs missing mapping fields.")
        send_mapping_alert_email(mapping_file_name=mapping_file, missing_ids=missing_ids)
        archive_batch_files(sftp, source_file, move_file=True, source_lookup=source_lookup)

    # ------------------- Phase 5: Build Master DataFrame -------------------
    master = build_master_dataframe(dfs)
    # Replace NaN with empty string to avoid errors in payload generation
    master.fillna("", inplace=True)
    # ------------------- Phase 5a: Safety Check on IDs -------------------
    if not master.empty:
        logging.info("[SAFETY CHECK] Verifying PeopleStrong IDs and ERP IDs")

        # Check PeopleStrongID format
        invalid_ps_ids = master[~master[JOIN_KEY].astype(str).str.startswith("PH")]
        if not invalid_ps_ids.empty:
            logging.warning(f"[ALERT] {len(invalid_ps_ids)} PeopleStrong IDs do not start with 'PH'. Please verify these IDs:")
            print(invalid_ps_ids[[JOIN_KEY, "ERPID"]])

        

        logging.info(f"[SAFETY CHECK] ERP IDs verified for {len(master)} candidates")

        dump_df(master, "RPA_Master_File")  
    all_mapping_ids = mapping_df[JOIN_KEY].tolist()

    if master.empty:
        logging.warning("[ALERT] Mapping present but no matching candidate data found.")
        send_no_data_alert(mapping_file, all_mapping_ids)
        record_pending_ids(db_conn, all_mapping_ids)
        archive_batch_files(sftp, source_file, move_file=True, source_lookup=source_lookup)
        sftp.close()
        ssh.close()
        logging.info("===== PROCESS COMPLETE =====")
        return

    # ------------------- Phase 6: Process Candidates -------------------
    push_data = []
    max_rows = max_ids if isinstance(max_ids, int) and max_ids > 0 else None
    if max_rows:
        logging.info(f"[LIMIT] Push main processing limited to first {max_rows} candidate(s).")

    rows_to_process = master.head(max_rows) if max_rows else master
    for _, r in rows_to_process.iterrows():
        cid = r[JOIN_KEY]
        erpid = safe(r.get("ERPID"))

        logging.info("-" * 60)
        logging.info(f"[PHASE 6] Processing Candidate: {cid}")

        if should_skip_push(cid, mapping_file):
            logging.info(f"[SKIP] Candidate {cid} already pushed for mapping file {mapping_file}. Skipping duplicate push.")
            update_push_tracking(
                candidate_row=r,
                candidate_id=cid,
                erpid=erpid,
                erp_valid=True,
                mapping_file=mapping_file,
                batch_date=batch_date_value,
                status=STATUS_SUCCESS,
                db_overall_status=STATUS_SUCCESS,
                db_erp_done=1,
                comments="Skipped duplicate push for same mapping file",
                db_comments="Skipped duplicate push for same mapping file"
            )
            continue

        # ------------------- Phase 6a: ERP ID Validation -------------------
        erp_valid = bool(erpid and is_erp_id_valid(erpid))
        if not erp_valid:
            logging.warning(f"[SKIP] ERPID invalid or not found in ERP — skipping candidate: {cid} | ERPID: {erpid}")
            save_to_queue(candidate_id=cid,
                          erpid=erpid,
                          overall_status=STATUS_PENDING,
                          comments="ERP ID invalid or not found — pending",
                          db_conn=db_conn)
            update_push_tracking(
                candidate_row=r,
                candidate_id=cid,
                erpid=erpid,
                erp_valid=False,
                mapping_file=mapping_file,
                batch_date=batch_date_value,
                status=STATUS_PENDING,
                db_overall_status=STATUS_PENDING,
                db_erp_done=0,
                comments="ERP ID invalid or not found — pending",
                db_comments="ERP ID invalid or not found — pending"
            )
            push_data.append({"CandidateID": cid, "ERPID": erpid ,
                              "status": STATUS_FAILED,
                              "comments": "ERP ID invalid or not found — pending"})
            continue

        # Fetch pending candidate state from DB
   

        logging.info(f"[INFO] Fetching pending candidates for current batch IDs: {all_mapping_ids}")
        pending = fetch_recent_pending_candidates(db_conn=db_conn, recent_ids=all_mapping_ids)
        logging.info(f"[INFO] Found {len(pending)} pending candidates in DB for this batch")
        candidate_in_db = next((c for c in pending if c[0] == cid), None)

        if candidate_in_db:
            _, erpid_db, batch_date, Text_payload, File_Payload, text_done, file_done, erp_done, overall_status, comments, _, mapping_file = candidate_in_db
            logging.info(f"[Mapping] Candidate {cid} found in DB. Resuming last state.")
        else:
            Text_payload = File_Payload = None
            text_done = file_done = erp_done = 0
            overall_status = STATUS_PENDING
            comments = None

        if isinstance(Text_payload, str) and Text_payload.strip():
            try:
                Text_payload = json.loads(Text_payload)
            except Exception:
                pass

        push_track_row = get_push_tracking_row(cid) or {}
        text_already_prepared = bool(text_done) or str(push_track_row.get("Text Payload Ready") or "").strip().lower() == "yes"
        docs_already_prepared = bool(file_done) or str(push_track_row.get("Documents Ready") or "").strip().lower() == "yes"

        print_peoplestrong_snapshot(r)

        # ------------------- Phase 6b: Prepare Payloads -------------------
        try:
            build_text_payload = not text_already_prepared
            build_file_payload = not docs_already_prepared

            if build_text_payload and build_file_payload:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_text = executor.submit(build_erp_payload, r)
                    future_docs = executor.submit(get_candidate_document_links, cid)
                    Text_payload = future_text.result()
                    File_Payload = future_docs.result()
            elif build_text_payload:
                Text_payload = build_erp_payload(r)
            elif build_file_payload:
                File_Payload = get_candidate_document_links(cid)

            if build_text_payload or build_file_payload:
                save_to_queue(candidate_id=cid, erpid=erpid,
                              text_payload=json.dumps(Text_payload) if build_text_payload and Text_payload else None,
                              db_conn=db_conn,
                              batch_date=batch_date,
                              mapping_file=mapping_file,
                              source_file=json.dumps(source_file),
                              text_done=1 if build_text_payload and Text_payload else None,
                              file_done=1 if build_file_payload and File_Payload else None,
                              erp_done=None,
                              overall_status=overall_status)

            text_ready_for_tracking = Text_payload if Text_payload else text_already_prepared
            docs_ready_for_tracking = File_Payload if File_Payload else docs_already_prepared

            update_push_tracking(
                candidate_row=r,
                candidate_id=cid,
                erpid=erpid,
                erp_valid=True,
                mapping_file=mapping_file,
                batch_date=batch_date_value,
                text_payload=text_ready_for_tracking,
                file_payload=docs_ready_for_tracking,
                status=overall_status,
                db_overall_status=overall_status,
                db_erp_done=erp_done,
                comments=comments,
                db_comments=comments
            )

            logging.info("[PHASE 6b] Text payload and document links ready")
        except Exception as e:
            logging.error(f"[ERROR] Failed to prepare payload/docs for {cid}: {e}")
            save_to_queue(candidate_id=cid, erpid=erpid,
                          overall_status=STATUS_FAILED,
                          comments=f"Payload/Document prep failed: {str(e)}",
                          db_conn=db_conn)
            update_push_tracking(
                candidate_row=r,
                candidate_id=cid,
                erpid=erpid,
                erp_valid=True,
                mapping_file=mapping_file,
                batch_date=batch_date_value,
                status=STATUS_FAILED,
                db_overall_status=STATUS_FAILED,
                db_erp_done=0,
                comments=f"Payload/Document prep failed: {str(e)}",
                db_comments=f"Payload/Document prep failed: {str(e)}"
            )
            push_data.append({"CandidateID": cid, "ERPID": erpid, "status": STATUS_FAILED,
                              "comments": f"Payload/Document prep failed: {str(e)}"})
            continue

        # ------------------- Phase 6c: Push to ERP -------------------
        try:
            if not erp_done:
                if str(overall_status or "").strip().upper() == "TEXT_SENT":
                    if not File_Payload:
                        File_Payload = get_candidate_document_links(cid)
                    status, resp = send_to_erp(erpid=erpid, payload_data=None, file_data=File_Payload)
                else:
                    if not Text_payload:
                        Text_payload = build_erp_payload(r)
                    if File_Payload is None:
                        File_Payload = get_candidate_document_links(cid)
                    status, resp = send_to_erp(erpid=erpid, payload_data=Text_payload, file_data=File_Payload)
                
                bot_comment = "Synced Successfully" if status == STATUS_SUCCESS else f"Failed: {resp}"

                save_to_queue(candidate_id=cid, erpid=erpid,
                              erp_done=1 if status == STATUS_SUCCESS else 0,
                              overall_status=status,
                              comments=bot_comment,
                              db_conn=db_conn)

                logging.info(f"[PHASE 6c] ERP Status={status} | ERPID={erpid}")
                print(f"[PHASE 6c] ERP Response: {resp}")
            else:
                logging.info(f"[SKIP] ERP already done for {cid}")
                status = STATUS_SUCCESS
                bot_comment = "Already Synced"

            update_push_tracking(
                candidate_row=r,
                candidate_id=cid,
                erpid=erpid,
                erp_valid=True,
                mapping_file=mapping_file,
                batch_date=batch_date_value,
                text_payload=Text_payload,
                file_payload=File_Payload,
                status=status,
                db_overall_status=status,
                db_erp_done=1 if status == STATUS_SUCCESS else 0,
                comments=bot_comment,
                db_comments=bot_comment
            )
        except Exception as e:
            logging.error(f"[ERROR] ERP push failed for {erpid}: {e}")
            status = STATUS_FAILED
            bot_comment = f"ERP push exception: {str(e)}"
            save_to_queue(candidate_id=cid, erpid=erpid,
                          overall_status=status,
                          comments=bot_comment,
                          db_conn=db_conn)
            update_push_tracking(
                candidate_row=r,
                candidate_id=cid,
                erpid=erpid,
                erp_valid=True,
                mapping_file=mapping_file,
                batch_date=batch_date_value,
                text_payload=Text_payload,
                file_payload=File_Payload,
                status=status,
                db_overall_status=status,
                db_erp_done=0,
                comments=bot_comment,
                db_comments=bot_comment
            )

        push_data.append({"CandidateID": cid, "ERPID": erpid, "status": status, "comments": bot_comment})

    # ------------------- Phase 7: Archive Batch Files -------------------
    if push_data:
        all_success = all(item["status"] == STATUS_SUCCESS for item in push_data)
        archive_batch_files(sftp, source_file, move_file=all_success, source_lookup=source_lookup)
        logging.info(f"[ARCHIVE] Batch files {'moved permanently' if all_success else 'kept temporarily for reprocessing'}")
    else:
        logging.warning("[ARCHIVE] No candidates processed. Skipping archive.")

    # ------------------- Phase 7b: Sync local data_master to SFTP debugging -------------------
    try:
        sync_data_master_to_sftp_debugging(sftp)
    except Exception as e:
        logging.error(f"[DEBUGGING] Failed to sync data_master to SFTP debugging folder: {e}")

    # ------------------- Phase 8: Close SFTP -------------------
    try:
        sftp.close()
        ssh.close()
    except Exception as e:
        logging.error("Failed to close SFTP/SSH connections: %s", str(e))

    # ------------------- Phase 9: Send Push Summary -------------------
    if push_data:
        all_success = all(item["status"] == STATUS_SUCCESS for item in push_data)
        if all_success:
            logging.info("[PHASE 9] All candidates synced successfully. Sending push summary email...")
            send_push_summary_email(push_data)
        else:
            logging.info("[PHASE 9] Not all candidates synced successfully. Sending ERP error summary...")
            send_erp_error_summary(push_data)

    # ------------------- Phase 10: Batch Summary -------------------
    total_candidates = len(push_data)
    success_count = sum(1 for x in push_data if x["status"] == STATUS_SUCCESS)
    pending_count = sum(1 for x in push_data if x["status"] == STATUS_PENDING)
    failed_count = sum(1 for x in push_data if x["status"] == STATUS_FAILED)

    logging.info("=" * 80)
    logging.info(f"BATCH SUMMARY → Total: {total_candidates} | Success: {success_count} | Pending: {pending_count} | Failed: {failed_count}")
    logging.info("=" * 80)
    print(f"\nBATCH SUMMARY → Total: {total_candidates} | Success: {success_count} | Pending: {pending_count} | Failed: {failed_count}\n")

    logging.info("===== PROCESS COMPLETE =====")
    if own_conn and db_conn:
        try:
            db_conn.close()
        except Exception:
            pass