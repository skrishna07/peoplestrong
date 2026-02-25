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
from concurrent.futures import ThreadPoolExecutor

REPORT_FILE = "PeopleStrong_Master_Report.xlsx"


# =================== Helper Functions =====================

def archive_batch_files(sftp, files, move_file=True):
    for f_name in files:
        try:
            safe_archive_file(sftp, f"{IMPORT_DIR}/{f_name}", ARCHIVE_DIR, move_file=move_file)
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

def PS_to_ERP_Push(db_conn=None):
    logging.info("===== PEOPLESTRONG → ERP START =====")
    logging.info(f"Job Started At: {datetime.now()}")

    # ------------------- Phase 1: Initialize DB -------------------
    try:
        init_db(db_conn=db_conn)
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
        Push_Pending()
    except Exception as e:
        logging.error(f"[PENDING] Failed to process pending queue: {e}")

    # ------------------- Phase 3: Load CSVs -------------------
    logging.info("[PHASE 3] Loading CSVs...")
    try:
        dfs, batch_date, mapping_file, source_file = load_csvs(sftp)
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
        archive_batch_files(sftp, source_file, move_file=True)
        sftp.close()
        ssh.close()
        return

    mapping_df[JOIN_KEY] = mapping_df[JOIN_KEY].astype(str).str.strip()

    missing_ids = mapping_df[mapping_df[JOIN_KEY].isna()][JOIN_KEY].tolist()
    if missing_ids:
        logging.warning(f"[ALERT] {len(missing_ids)} candidate IDs missing mapping fields.")
        send_mapping_alert_email(mapping_file_name=mapping_file, missing_ids=missing_ids)
        archive_batch_files(sftp, source_file, move_file=True)

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
        archive_batch_files(sftp, source_file, move_file=True)
        sftp.close()
        ssh.close()
        logging.info("===== PROCESS COMPLETE =====")
        return

    # ------------------- Phase 6: Process Candidates -------------------
    push_data = []
    for _, r in master.iterrows():
        cid = r[JOIN_KEY]
        erpid = safe(r.get(JOIN_KEY))

        logging.info("-" * 60)
        logging.info(f"[PHASE 6] Processing Candidate: {cid}")

        # ------------------- Phase 6a: ERP ID Validation -------------------
        if not erpid or not is_erp_id_valid(erpid):
            logging.warning(f"[SKIP] ERPID invalid or not found in ERP — skipping candidate: {cid} | ERPID: {erpid}")
            save_to_queue(candidate_id=cid,
                          erpid=erpid,
                          overall_status=STATUS_PENDING,
                          comments="ERP ID invalid or not found — pending",
                          db_conn=db_conn)
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

        print_peoplestrong_snapshot(r)

        # ------------------- Phase 6b: Prepare Payloads -------------------
        try:
            if not Text_payload or not File_Payload:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_text = executor.submit(build_erp_payload, r)
                    future_docs = executor.submit(get_candidate_document_links, cid)
                    Text_payload = future_text.result()
                    File_Payload = future_docs.result()

                save_to_queue(candidate_id=cid, erpid=erpid,
                              text_payload=json.dumps(Text_payload),
                              db_conn=db_conn,
                              batch_date=batch_date,
                              mapping_file=mapping_file,
                              source_file=json.dumps(source_file),
                              text_done=1 if Text_payload else 0,
                              file_done=1 if File_Payload else 0,
                              erp_done=0,
                              overall_status=overall_status)

            logging.info("[PHASE 6b] Text payload and document links ready")
        except Exception as e:
            logging.error(f"[ERROR] Failed to prepare payload/docs for {cid}: {e}")
            save_to_queue(candidate_id=cid, erpid=erpid,
                          overall_status=STATUS_FAILED,
                          comments=f"Payload/Document prep failed: {str(e)}",
                          db_conn=db_conn)
            push_data.append({"CandidateID": cid, "ERPID": erpid, "status": STATUS_FAILED,
                              "comments": f"Payload/Document prep failed: {str(e)}"})
            continue

        # ------------------- Phase 6c: Push to ERP -------------------
        try:
            if not erp_done:
                status, resp = send_to_erp(erpid=cid, payload_data=Text_payload, file_data=File_Payload)
                
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
        except Exception as e:
            logging.error(f"[ERROR] ERP push failed for {erpid}: {e}")
            status = STATUS_FAILED
            bot_comment = f"ERP push exception: {str(e)}"
            save_to_queue(candidate_id=cid, erpid=erpid,
                          overall_status=status,
                          comments=bot_comment,
                          db_conn=db_conn)

        push_data.append({"CandidateID": cid, "ERPID": erpid, "status": status, "comments": bot_comment})

    # ------------------- Phase 7: Archive Batch Files -------------------
    if push_data:
        all_success = all(item["status"] == STATUS_SUCCESS for item in push_data)
        archive_batch_files(sftp, source_file, move_file=all_success)
        logging.info(f"[ARCHIVE] Batch files {'moved permanently' if all_success else 'kept temporarily for reprocessing'}")
    else:
        logging.warning("[ARCHIVE] No candidates processed. Skipping archive.")

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
