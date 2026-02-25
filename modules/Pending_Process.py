
from libraries import *
from modules.Helpers import *
from modules.Text_Field_Validator import *
from modules.Files_Field_Validator import *
from modules.Sql_Helper import *
from modules.Pending_Process import *
from modules.Csv_File_Handler import *
from api_handler.Ps_to_Erp_Requestor import send_to_erp,is_erp_id_valid
from modules.Document_Base64_Generator import get_candidate_document_links
from modules.ERP_Builder import *





def rebuild_payload_from_batch(sftp, batch_date, source_files, candidate_id):
    """
    Rebuilds text & file payloads for ONE candidate using batch CSV files.
    Applies same normalization logic as build_master_dataframe().
    """

    logging.info(f"[REBUILD] Starting rebuild for Candidate: {candidate_id}")

    dfs = {}

    # ---------------- LOAD & FILTER CSV FILES ----------------
    for file_name in source_files:
        df = None

        for dir_path in [IMPORT_DIR, ARCHIVE_DIR]:
            try:
                path = f"{dir_path}/{file_name}"
                with sftp.open(path, "rb") as fh:
                    if "Contact" in file_name:
                        df = robust_pipe_reader(fh)
                    else:
                        df = pd.read_csv(io.BytesIO(fh.read()), sep="|", dtype=str)

                df.columns = df.columns.str.strip()
                break
            except FileNotFoundError:
                continue

        if df is None or JOIN_KEY not in df.columns:
            continue

        df[JOIN_KEY] = df[JOIN_KEY].astype(str).str.strip()
        df = df[df[JOIN_KEY] == str(candidate_id)]

        if df.empty:
            continue

        prefix = next((p for p in [
            "CandidateData",
            "CandidateContact",
            "CandidateEducation",
            "CandidateEmergencyContact",
            "CandidateIDDetails",
            "CandidateSalaryData"
        ] if file_name.startswith(p)), None)

        if prefix:
            dfs[prefix] = df

    # ---------------- BASE TABLE ----------------
    master = dfs.get("CandidateData")
    if master is None or master.empty:
        logging.error(f"[ERROR] No CandidateData found for {candidate_id}")
        return pd.DataFrame(), pd.DataFrame()

    # ---------------- EDUCATION ----------------
    edu_df = dfs.get("CandidateEducation")
    if edu_df is not None and not edu_df.empty:
        edu_df = normalize_education(edu_df)
        master = master.merge(edu_df, on=JOIN_KEY, how="left")

    # ---------------- EMERGENCY CONTACT ----------------
    emergency_df = dfs.get("CandidateEmergencyContact")
    if emergency_df is not None and not emergency_df.empty:
        master = master.merge(emergency_df, on=JOIN_KEY, how="left")

    # ---------------- ID DETAILS ----------------
    id_df = dfs.get("CandidateIDDetails")
    if id_df is not None and not id_df.empty:
        id_df = normalize_id(id_df)

        # Select main ID
        id_main_df = (
            id_df.groupby(JOIN_KEY, group_keys=False)
            .apply(lambda grp: select_id_type(grp, grp.name))
            .reset_index(drop=False)
        )

        master = master.merge(id_main_df, on=JOIN_KEY, how="left")

    # ---------------- SALARY ----------------
    sal_df = dfs.get("CandidateSalaryData")
    if sal_df is not None and not sal_df.empty:
        sal_df = normalize_salary(sal_df)
        master = master.merge(sal_df, on=JOIN_KEY, how="left")

    # ---------------- PRIMARY ADDRESS ----------------
    contact_df = dfs.get("CandidateContact")
    if contact_df is not None and not contact_df.empty:
        primary_address = select_primary_address(contact_df, candidate_id)

        if primary_address is not None:
            primary_address_df = pd.DataFrame([primary_address])
            master = master.merge(primary_address_df, on=JOIN_KEY, how="left")

    # ---------------- REMOVE DUPLICATES ----------------
    master = master.drop_duplicates(subset=[JOIN_KEY])

    try:
        text_payload = master
        text_payload = text_payload.replace({pd.NaT: None})
        text_payload = text_payload.where(pd.notnull(text_payload), None)
    except Exception as e:
        print("Text payload error as ",e)

    # ---------------- FILE PAYLOAD ----------------
    try:
        file_payload = get_candidate_document_links(candidate_id)
    except Exception:
        file_payload = {}

    # ---------------- WRITE DEBUG FILE ----------------
    output_path = f"debug_text_payload_{candidate_id}.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"Text Payload for Candidate: {candidate_id}\n")
        f.write("=" * 80 + "\n\n")

        if text_payload is not None and not text_payload.empty:
            f.write(text_payload.to_string(index=False))
        else:
            f.write("No data found.\n")

    print(f"[DEBUG] Text payload written to {output_path}")

    if text_payload is not None and not text_payload.empty:
        print_peoplestrong_snapshot(text_payload.iloc[0])

    return text_payload, file_payload




def fetch_pending_candidates(db_conn=None):
    """Fetch all candidates that are not fully synced (text/file/ERP)."""
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
            WHERE IFNULL(erp_done, 0) = 0
               OR IFNULL(text_done, 0) = 0
               OR IFNULL(file_done, 0) = 0
            ORDER BY created_at ASC
        """)

        rows = c.fetchall()

        if own_conn:
            db_conn.close()

        return rows

    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates: {e}")
        return []

def Push_Pending(db_conn=None):
    logging.info("========== PENDING PUSH START ==========")

    # -------------------- DB Initialization --------------------
    try:
        init_db(db_conn=db_conn)
        logging.info("[DB] Initialized successfully.")
    except Exception as e:
        logging.error(f"[DB ERROR] Initialization failed: {e}")
        return

    # -------------------- Fetch Pending Candidates --------------------
    pending_candidates = fetch_pending_candidates(db_conn=db_conn)
    if not pending_candidates:
        logging.info("[INFO] No pending candidates found.")
        return
    logging.info(f"[INFO] Found {len(pending_candidates)} pending candidates.")

    push_data = []

    # -------------------- Process Each Candidate --------------------
    for candidate in pending_candidates:
        try:
            (cid, erpid_db, batch_date, text_payload_db, file_payload_db,
             text_done, file_done, erp_done, overall_status,
             comments, source_file, mapping_file) = candidate

            logging.info("-" * 60)
            logging.info(f"[PROCESSING] Candidate: {cid} | ERP ID: {erpid_db} | Status: {overall_status}")

            # -------------------- ERP ID Validation --------------------
            erpid_valid = erpid_db and is_erp_id_valid(erpid_db)
            if not erpid_valid:
                logging.warning(f"[WARN] Candidate {cid} ERP ID missing or invalid")
                save_to_queue(candidate_id=cid, erpid=erpid_db or "N/A",
                              overall_status=STATUS_PENDING,
                              comments="ERP ID missing or invalid — waiting",
                              db_conn=db_conn)
                push_data.append({
                    "CandidateID": cid,
                    "ERPID": erpid_db or "N/A",
                    "status": STATUS_PENDING,
                    "comments": "ERP ID missing or invalid"
                })
                continue

            # -------------------- Rebuild Payload from Batch --------------------
            text_payload, file_payload = None, None

            if batch_date and source_file:
                try:
                    source_files = json.loads(source_file)
                    logging.debug(f"[DEBUG] Candidate {cid} source_files: {source_files}")
                except Exception as e:
                    logging.warning(f"[WARN] Candidate {cid} has invalid source_file JSON: {e}")
                    source_files = []

                if source_files:
                    ssh, sftp = get_sftp_connection()
                    try:
                        text_payload, file_payload = rebuild_payload_from_batch(
                            sftp=sftp,
                            batch_date=batch_date,
                            source_files=source_files,
                            candidate_id=cid
                        )
                        logging.debug(f"[DEBUG] Candidate {cid} rebuilt text_payload type: {type(text_payload)}, file_payload type: {type(file_payload)}")
                    except Exception as e:
                        logging.error(f"[ERROR] Candidate {cid} payload rebuild failed: {e}")
                    finally:
                        sftp.close()
                        ssh.close()

                    # Convert DataFrame to dict for JSON serialization
                    if text_payload is not None and hasattr(text_payload, 'iloc'):
                        if not text_payload.empty:
                            try:
                                text_payload_dict = text_payload.iloc[0].to_dict()
                                logging.debug(f"[DEBUG] Candidate {cid} text_payload_dict: {text_payload_dict}")
                            except Exception as e:
                                logging.error(f"[ERROR] Candidate {cid} text_payload conversion failed: {e}")
                                text_payload_dict = None
                        else:
                            text_payload_dict = None
                    else:
                        text_payload_dict = text_payload  # in case already dict

                    text_done = 1 if text_payload_dict else 0
                    file_done = 1 if file_payload else 0

                    # Save rebuilt payload to queue
                    save_to_queue(
                        candidate_id=cid,
                        erpid=erpid_db,
                        text_payload=json.dumps(text_payload_dict) if text_payload_dict else None,
                        text_done=text_done,
                        file_done=file_done,
                        overall_status=STATUS_PENDING if erp_done == 0 else STATUS_SUCCESS,
                        db_conn=db_conn
                    )
                    logging.info(f"[PAYLOAD] Candidate {cid} → text_done={text_done}, file_done={file_done}")

                else:
                    logging.warning(f"[WARN] Candidate {cid} has no valid source files")
                    save_to_queue(candidate_id=cid, erpid=erpid_db,
                                  text_done=text_done, file_done=file_done,
                                  overall_status=STATUS_PENDING,
                                  comments="No valid source files for rebuild",
                                  db_conn=db_conn)
                    push_data.append({
                        "CandidateID": cid, "ERPID": erpid_db,
                        "status": STATUS_PENDING,
                        "comments": "No valid source files for rebuild"
                    })
                    continue

            else:
                logging.warning(f"[WARN] Candidate {cid} missing batch_date or source_file")
                save_to_queue(candidate_id=cid, erpid=erpid_db,
                              text_done=text_done, file_done=file_done,
                              overall_status=STATUS_PENDING,
                              comments="Missing batch info — cannot rebuild payloads",
                              db_conn=db_conn)
                push_data.append({
                    "CandidateID": cid, "ERPID": erpid_db,
                    "status": STATUS_PENDING,
                    "comments": "Missing batch info — cannot rebuild payloads"
                })
                continue

            # -------------------- ERP Push --------------------
            if text_done and erp_done != 1:
                try:
                    logging.debug(f"[DEBUG] Candidate {cid} sending ERP push: payload type={type(text_payload_dict)}, file type={type(file_payload)}")
                    text_payload_dict = build_erp_payload(text_payload.iloc[0]) if text_payload is not None else None
                    status, response = send_to_erp(erpid_db,
                                                   payload_data=text_payload_dict,
                                                   file_data=file_payload)
                    overall_status = STATUS_SUCCESS if status == STATUS_SUCCESS and file_payload else STATUS_PENDING
                    erp_done = 1 if overall_status == STATUS_SUCCESS else 0

                    save_to_queue(candidate_id=cid,
                                  erpid=erpid_db,
                                  erp_done=erp_done,
                                  overall_status=status,
                                  comments=response,
                                  db_conn=db_conn)
                    logging.info(f"[ERP PUSH] Candidate {cid} → {status} | Response: {response}")
                    push_data.append({"CandidateID": cid, "ERPID": erpid_db, "status": status, "comments": response})
                except Exception as e:
                    logging.error(f"[ERP PUSH ERROR] Candidate {cid} → {e}")
                    save_to_queue(candidate_id=cid,
                                  erp_done=0,
                                  overall_status=STATUS_FAILED,
                                  comments=f"ERP push failed: {e}",
                                  db_conn=db_conn)
                    push_data.append({"CandidateID": cid, "ERPID": erpid_db, "status": STATUS_FAILED, "comments": str(e)})
            else:
                logging.info(f"[SKIP] ERP push skipped for Candidate {cid}: text_done={text_done}, file_done={file_done}, erp_done={erp_done}")
                push_data.append({"CandidateID": cid, "ERPID": erpid_db, "status": STATUS_PENDING, "comments": "Pending for ERP push"})

        except Exception as e:
            logging.error(f"[ERROR] Candidate {cid} failed: {e}")
            save_to_queue(candidate_id=cid, erpid=erpid_db or "N/A",
                          overall_status=STATUS_FAILED, comments=str(e),
                          db_conn=db_conn)
            push_data.append({"CandidateID": cid, "ERPID": erpid_db or "N/A", "status": STATUS_FAILED, "comments": str(e)})

    # -------------------- Phase 4: Pending Summary --------------------
    if push_data:
        total = len(push_data)
        success_count = sum(1 for x in push_data if x["status"] == STATUS_SUCCESS)
        pending_count = sum(1 for x in push_data if x["status"] == STATUS_PENDING)
        failed_count = sum(1 for x in push_data if x["status"] == STATUS_FAILED)

        logging.info("=" * 80)
        logging.info("PENDING PROCESS SUMMARY")
        logging.info(f"Total Processed: {total}")
        logging.info(f"Success: {success_count}")
        logging.info(f"Still Pending: {pending_count}")
        logging.info(f"Failed: {failed_count}")
        logging.info("-" * 80)

        # Reason breakdown
        reason_counter = {}
        for item in push_data:
            reason = item.get("comments") or "No Comments"
            reason_counter[reason] = reason_counter.get(reason, 0) + 1

        logging.info("Reason Breakdown:")
        for reason, count in reason_counter.items():
            logging.info(f" - {reason} → {count}")

        logging.info("=" * 80)
    else:
        logging.info("[SUMMARY] No pending candidates were processed.")

    logging.info("========== PENDING PUSH COMPLETE ==========")

if __name__=='__main__':
    Push_Pending()
else:
    print("Error")