
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

def _has_payload_data(value):
    if value is None:
        return False
    if isinstance(value, pd.DataFrame):
        return not value.empty
    if isinstance(value, (dict, list, tuple, set, str)):
        return len(value) > 0
    try:
        return bool(value)
    except Exception:
        return False





def rebuild_payload_from_batch(sftp, batch_date, source_files, candidate_id, build_text=True, build_files=True):
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

    text_payload = pd.DataFrame()
    if build_text:
        # ---------------- BASE TABLE ----------------
        master = dfs.get("CandidateData")
        if master is None or master.empty:
            logging.error(f"[ERROR] No CandidateData found for {candidate_id}")
            return pd.DataFrame(), {}

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
        file_payload = get_candidate_document_links(candidate_id) if build_files else {}
    except Exception:
        file_payload = {}

    # ---------------- WRITE DEBUG FILE ----------------
    if build_text:
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
            WHERE (IFNULL(erp_done, 0) = 0
               OR IFNULL(text_done, 0) = 0
               OR IFNULL(file_done, 0) = 0)
            AND overall_status != 'Dropped'
            ORDER BY created_at ASC
        """)

        rows = c.fetchall()

        if own_conn:
            db_conn.close()

        return rows

    except Exception as e:
        logging.error(f"[DB] Failed to fetch pending candidates: {e}")
        return []


_erp_validation_cache = {}

def batch_validate_erp_ids(erpid_list):
    """Validate multiple ERP IDs in parallel. Cache results locally to avoid re-checking."""
    from concurrent.futures import ThreadPoolExecutor, as_completed
    results = {}
    to_check = [eid for eid in erpid_list if eid not in _erp_validation_cache]
    
    if not to_check:
        return {eid: _erp_validation_cache[eid] for eid in erpid_list}
    
    def _check(eid):
        try:
            valid = is_erp_id_valid(eid)
            _erp_validation_cache[eid] = valid
            return eid, valid
        except Exception as e:
            logging.warning(f"[ERP CACHE] Validation error for {eid}: {e}")
            _erp_validation_cache[eid] = False
            return eid, False
    
    with ThreadPoolExecutor(max_workers=5) as executor:
        futures = {executor.submit(_check, eid): eid for eid in to_check}
        for future in as_completed(futures):
            try:
                eid, valid = future.result(timeout=30)
                results[eid] = valid
            except Exception as e:
                eid = futures[future]
                logging.error(f"[ERP CACHE] Timeout/error for {eid}: {e}")
                results[eid] = False
    
    return {**{eid: _erp_validation_cache[eid] for eid in erpid_list if eid in _erp_validation_cache}, **results}

def Push_Pending(db_conn=None, max_ids=None):
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

    if isinstance(max_ids, int) and max_ids > 0:
        pending_candidates = pending_candidates[:max_ids]
        logging.info(f"[LIMIT] Pending processing limited to first {len(pending_candidates)} candidate(s).")

    logging.info(f"[INFO] Found {len(pending_candidates)} pending candidates.")
    
    # -------------------- Batch ERP Validation (Parallel) --------------------
    erpid_list = [c[1] for c in pending_candidates if c[1]]
    logging.info(f"[INFO] Pre-validating {len(erpid_list)} ERP IDs in parallel...")
    erp_validation_map = batch_validate_erp_ids(erpid_list)
    logging.info(f"[INFO] ERP validation complete. Cached {len(_erp_validation_cache)} results.")
    
    push_data = []

    # -------------------- Process Each Candidate --------------------
    for candidate in pending_candidates:
        try:
            (cid, erpid_db, batch_date, text_payload_db, file_payload_db,
             text_done, file_done, erp_done, overall_status,
             comments, source_file, mapping_file) = candidate

            logging.info("-" * 60)
            logging.info(f"[PROCESSING] Candidate: {cid} | ERP ID: {erpid_db} | Status: {overall_status}")

            # -------------------- ERP ID Validation (from cache) --------------------
            erpid_valid = erpid_db and erp_validation_map.get(erpid_db, False)
            if not erpid_valid:
                logging.warning(f"[WARN] Candidate {cid} ERP ID missing or invalid (cached)")
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
            text_payload_dict = None

            if text_payload_db and text_done == 1:
                try:
                    text_payload_dict = json.loads(text_payload_db)
                    text_payload = pd.DataFrame([text_payload_dict])
                except Exception as parse_err:
                    logging.warning(f"[WARN] Candidate {cid} stored payload parse error: {parse_err}")

            if batch_date and source_file:
                try:
                    source_files = json.loads(source_file)
                except Exception:
                    source_files = []

                if source_files:
                    build_text = not text_done
                    build_files = not file_done

                    if build_text or build_files:
                        ssh, sftp = get_sftp_connection()
                        try:
                            rebuilt_text_payload, rebuilt_file_payload = rebuild_payload_from_batch(
                                sftp=sftp,
                                batch_date=batch_date,
                                source_files=source_files,
                                candidate_id=cid,
                                build_text=build_text,
                                build_files=build_files
                            )
                        finally:
                            sftp.close()
                            ssh.close()

                        if build_text:
                            text_payload = rebuilt_text_payload
                        if build_files:
                            file_payload = rebuilt_file_payload

                    elif overall_status == "TEXT_SENT" and erp_done == 0:
                        file_payload = get_candidate_document_links(cid)

                    # Convert DataFrame to dict
                    if text_payload is not None and not text_payload.empty:
                        text_payload_dict = text_payload.iloc[0].to_dict()

                    text_done = 1 if text_done or _has_payload_data(text_payload_dict) else 0
                    file_done = 1 if file_done or _has_payload_data(file_payload) else 0

                    save_to_queue(
                        candidate_id=cid,
                        erpid=erpid_db,
                        text_payload=json.dumps(text_payload_dict) if text_payload_dict else None,
                        text_done=text_done if _has_payload_data(text_payload_dict) else None,
                        file_done=file_done if _has_payload_data(file_payload) else None,
                        overall_status=STATUS_PENDING if erp_done == 0 else STATUS_SUCCESS,
                        db_conn=db_conn
                    )

                    logging.info(f"[PAYLOAD] Candidate {cid} → text_done={text_done}, file_done={file_done}")

                else:
                    logging.warning(f"[WARN] Candidate {cid} has no valid source files")
                    continue
            else:
                # No batch source info — try to recover from stored text_payload in DB
                if text_payload_db and text_done == 1:
                    logging.info(f"[RECOVERY] Candidate {cid} has no batch_date/source_file — using stored text_payload from DB.")
                    try:
                        text_payload_dict = json.loads(text_payload_db)
                        text_payload = pd.DataFrame([text_payload_dict])
                        if overall_status == "TEXT_SENT" and erp_done == 0:
                            file_payload = get_candidate_document_links(cid)
                        else:
                            file_payload = {}
                    except Exception as parse_err:
                        logging.warning(f"[WARN] Candidate {cid} stored payload parse error: {parse_err}")
                        push_data.append({
                            "CandidateID": cid, "ERPID": erpid_db,
                            "status": STATUS_PENDING, "comments": "Stored payload parse error"
                        })
                        continue
                else:
                    logging.warning(f"[WARN] Candidate {cid} missing batch_date/source_file and no stored payload — skipping for now.")
                    push_data.append({
                        "CandidateID": cid, "ERPID": erpid_db,
                        "status": STATUS_PENDING, "comments": "Missing batch_date/source_file — awaiting next batch"
                    })
                    continue

            # -------------------- ERP Push --------------------

            # CASE 1: Send TEXT first (only once)
            if text_done == 1 and erp_done == 0 and overall_status != "TEXT_SENT":
                try:
                    logging.info(f"[ERP TEXT PUSH] Sending TEXT for {cid}")

                    payload = build_erp_payload(text_payload.iloc[0])

                    status, response = send_to_erp(
                        erpid_db,
                        payload_data=payload,
                        file_data=None
                    )

                    if status == STATUS_SUCCESS:
                        overall_status = "TEXT_SENT"
                    else:
                        overall_status = STATUS_PENDING

                    save_to_queue(
                        candidate_id=cid,
                        erpid=erpid_db,
                        overall_status=overall_status,
                        comments=response,
                        db_conn=db_conn
                    )

                    push_data.append({
                        "CandidateID": cid,
                        "ERPID": erpid_db,
                        "status": overall_status,
                        "comments": response
                    })

                except Exception as e:
                    logging.error(f"[ERP TEXT ERROR] Candidate {cid} → {e}")
                    save_to_queue(candidate_id=cid,
                                  overall_status=STATUS_PENDING,
                                  comments=str(e),
                                  db_conn=db_conn)

            # CASE 2: File available later → Send FILE
            elif file_done == 1 and erp_done == 0:
                try:
                    logging.info(f"[ERP FILE PUSH] Sending FILE for {cid}")

                    status, response = send_to_erp(
                        erpid_db,
                        payload_data=None,
                        file_data=file_payload
                    )

                    if status == STATUS_SUCCESS:
                        erp_done = 1
                        overall_status = STATUS_SUCCESS
                    else:
                        erp_done = 0
                        overall_status = STATUS_PENDING

                    save_to_queue(
                        candidate_id=cid,
                        erpid=erpid_db,
                        erp_done=erp_done,
                        overall_status=overall_status,
                        comments=response,
                        db_conn=db_conn
                    )

                    push_data.append({
                        "CandidateID": cid,
                        "ERPID": erpid_db,
                        "status": overall_status,
                        "comments": response
                    })

                except Exception as e:
                    logging.error(f"[ERP FILE ERROR] Candidate {cid} → {e}")
                    save_to_queue(candidate_id=cid,
                                  erp_done=0,
                                  overall_status=STATUS_PENDING,
                                  comments=str(e),
                                  db_conn=db_conn)

            # CASE 3: Waiting
            else:
                logging.info(f"[WAITING] Candidate {cid} waiting for remaining data.")
                push_data.append({
                    "CandidateID": cid,
                    "ERPID": erpid_db,
                    "status": STATUS_PENDING,
                    "comments": "Waiting for remaining data"
                })

        except Exception as e:
            logging.error(f"[ERROR] Candidate {cid} failed: {e}")
            save_to_queue(candidate_id=cid,
                          erpid=erpid_db or "N/A",
                          overall_status=STATUS_FAILED,
                          comments=str(e),
                          db_conn=db_conn)

    # -------------------- Summary --------------------
    if push_data:
        total = len(push_data)
        success_count = sum(1 for x in push_data if x["status"] == STATUS_SUCCESS)
        pending_count = sum(1 for x in push_data if x["status"] == STATUS_PENDING)
        failed_count = sum(1 for x in push_data if x["status"] == STATUS_FAILED)

        logging.info("=" * 80)
        logging.info("PENDING PROCESS SUMMARY")
        logging.info(f"Total: {total}")
        logging.info(f"Success: {success_count}")
        logging.info(f"Pending: {pending_count}")
        logging.info(f"Failed: {failed_count}")
        logging.info("=" * 80)

    logging.info("========== PENDING PUSH COMPLETE ==========")