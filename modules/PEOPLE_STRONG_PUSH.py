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
from api_handler.Ps_to_Erp_Requestor import send_to_erp
from modules.Document_Base64_Generator import get_candidate_document_links
from modules.SEND_EMAIL_SUMMARY import send_push_summary_email,send_mapping_alert_email
from modules.Pending_Process import Push_Pending
from modules.ERP_Builder import build_erp_payload

# ============================================================
# CONFIG
# ============================================================

REPORT_FILE = "PeopleStrong_Master_Report.xlsx"






def PS_to_ERP_Push(db_conn=None):
    """
    Main automation function to push candidate data from PeopleStrong to ERP,
    tracking progress in SQLite pending_sync table.
    """
    logging.info("===== PEOPLESTRONG → ERP START =====")
    logging.info(f"Job Started At: {datetime.now()}")

    # ------------------- Initialize DB -------------------
    try:
        init_db(db_conn=db_conn)
    except Exception as e:
        logging.error("[DB] Database initialization failed: %s", str(e))
        print("Database Not Initialized")

    # ------------------- Connect SFTP -------------------
    try:
        ssh, sftp = get_sftp_connection()
        logging.info("[PHASE 1] SFTP connected")
    except Exception as e:
        logging.error("[SFTP] Connection failed: %s", str(e))
        return
    

    try:
        Push_Pending()
    except Exception as e:
        print(e)

    # ------------------- Load CSVs -------------------
    logging.info("===== PEOPLESTRONG → ERP  LIVE START =====")
    try:
        dfs, batch_date, mapping_file, source_file = load_csvs(sftp)
        mapping_df = dfs.get("Mapping")
    except Exception as e:
        logging.error("[CSV] Failed to load CSVs: %s", str(e))
        ssh.close()
        return

    # ------------------- Mapping Validation -------------------
    if mapping_df is None or mapping_df.empty:
        logging.warning("[ALERT] Mapping CSV is empty or missing candidate IDs. Automation stopped.")
        send_mapping_alert_email(mapping_file_name=str(mapping_file), missing_ids=None)
        logging.info("[ARCHIVE] Archiving invalid mapping batch...")
        print("sourcefiles",source_file)
        for f_name in source_file:
            try:
                safe_archive_file(sftp, f"{IMPORT_DIR}/{f_name}", ARCHIVE_DIR)
                logging.info("Archived: %s", f_name)
            except Exception as e:
                logging.error("ARCHIVE ERROR: %s", str(e))
        sftp.close()
        ssh.close()
        return

    mapping_df[JOIN_KEY] = mapping_df[JOIN_KEY].astype(str).str.strip()
    mapping_df["ERPID"] = mapping_df.get("ERPID", "").astype(str).str.strip()

    missing_ids = mapping_df[mapping_df[JOIN_KEY].isna() | mapping_df["ERPID"].isna()][JOIN_KEY].tolist()
    if missing_ids:
        logging.warning(f"[ALERT] {len(missing_ids)} candidate IDs missing mapping fields.")
        send_mapping_alert_email(mapping_file_name=mapping_file, missing_ids=missing_ids)
        logging.info("[ARCHIVE] Archiving invalid mapping batch...")
        print("sourcefiles",source_file)
        for f_name in source_file:
            try:
                safe_archive_file(sftp, f"{IMPORT_DIR}/{f_name}", ARCHIVE_DIR)
                logging.info("Archived: %s", f_name)
            except Exception as e:
                logging.error("ARCHIVE ERROR: %s", str(e))

    # ------------------- Build Master DataFrame -------------------
    master = build_master_dataframe(dfs)
    dump_df(master, "RPA_Master_File")

    push_data = []

    # ------------------- Process Candidates -------------------
    for _, r in master.iterrows():
        cid = r[JOIN_KEY]
        erpid = safe(r.get("ERPID"))

        logging.info("-" * 60)
        logging.info(f"[PHASE 5] Processing Candidate: {cid}")

        # Fetch pending candidates from DB
        pending = fetch_pending_candidates(db_conn=db_conn)
        candidate_in_db = next((c for c in pending if c[0] == cid), None)

        if candidate_in_db:
            # _, erpid_db, Text_payload, File_Payload, text_done, file_done, erp_done, overall_status, comments, _ = candidate_in_db
            _, erpid_db, Text_payload, File_Payload, text_done, file_done, erp_done, overall_status, comments, _, mapping_file = candidate_in_db

            logging.info(f"[Mapping] Candidate {cid} found in DB. Process starts from last state.")
        else:
            Text_payload = File_Payload = None
            text_done = file_done = erp_done = 0
            overall_status = STATUS_PENDING
            comments = None

        if not erpid:
            logging.warning("[SKIP] ERPID missing — skipping candidate")
            save_to_queue(candidate_id=cid, erpid="N/A", overall_status=STATUS_FAILED,
                          comments="Missing ERPID — skipped", db_conn=db_conn)
            push_data.append({"CandidateID": cid, "ERPID": "N/A", "status": STATUS_FAILED,
                              "comments": "Missing ERPID — skipped"})
            continue

        print_peoplestrong_snapshot(r)

        # ------------------- Prepare Payloads -------------------
        try:
            if not Text_payload or not File_Payload:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_text = executor.submit(build_erp_payload, r)
                    future_docs = executor.submit(get_candidate_document_links, cid)

                    Text_payload = future_text.result()
                    File_Payload = future_docs.result()
                    # File_Payload={}

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

            logging.info("[PHASE 6] Text payload and document links ready")
        except Exception as e:
            logging.error(f"[ERROR] Failed to prepare payload/docs for {cid}: {e}")
            save_to_queue(candidate_id=cid, erpid=erpid,
                          overall_status=STATUS_FAILED,
                          comments=f"Payload/Document prep failed: {str(e)}",
                          db_conn=db_conn)
            push_data.append({"CandidateID": cid, "ERPID": erpid, "status": STATUS_FAILED,
                              "comments": f"Payload/Document prep failed: {str(e)}"})
            continue

        #------------------- Push to ERP -------------------
        try:
            if not erp_done:
                status, resp = send_to_erp(erpid, payload_data=Text_payload, file_data=File_Payload)
                bot_comment = "Synced Successfully" if status == STATUS_SUCCESS else f"Failed: {resp}"

                save_to_queue(candidate_id=cid, erpid=erpid,
                              erp_done=1 if status == STATUS_SUCCESS else 0,
                              overall_status=status,
                              comments=bot_comment,
                              db_conn=db_conn)

                logging.info(f"[PHASE 7] ERP Status={status} | ERPID={erpid}")
                print(f"[PHASE 7] ERP Response: {resp}")
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

        logging.info("[STEP 5] Archiving files...")
        for f_name in source_file:
                try:
                    safe_archive_file(sftp, f"{IMPORT_DIR}/{f_name}", ARCHIVE_DIR)
                    logging.info("Archived: %s", f_name)
                except Exception as e:
                    logging.error("ARCHIVE ERROR: %s", str(e))

    # ------------------- Send Summary Email -------------------
    try:
        send_push_summary_email(push_data)
        logging.info(f"[SUMMARY] Sent summary email for {len(push_data)} candidates")
    except Exception as e:
        logging.error("Failed to send summary email: %s", str(e))

    # ------------------- Close SFTP -------------------
    try:
        sftp.close()
        ssh.close()
    except Exception as e:
        logging.error("Failed to close SFTP/SSH connections: %s", str(e))
    
    logging.info("===== PROCESS COMPLETE =====")




