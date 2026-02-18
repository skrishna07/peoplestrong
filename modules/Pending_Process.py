
from libraries import *
from modules.Helpers import *
from modules.Text_Field_Validator import *
from modules.Files_Field_Validator import *
from modules.Sql_Helper import *
from modules.Pending_Process import *
from modules.Csv_File_Handler import *
from api_handler.Ps_to_Erp_Requestor import send_to_erp
from modules.Document_Base64_Generator import get_candidate_document_links
from modules.ERP_Builder import *





def Push_Pending(db_conn=None):
    """
    Process all pending candidates from the database and push them to ERP.
    Only runs if there are pending candidates; otherwise exits gracefully.
    """

    logging.info("[PENDING] ===== PEOPLESTRONG → ERP PENDING START =====")
    logging.info(f"[PENDING] Job Started At: {datetime.now()}")

    # ------------------- Initialize DB -------------------
    try:
        init_db(db_conn=db_conn)
    except Exception as e:
        logging.error(f"[PENDING][DB] Database initialization failed: {e}")
        print("[PENDING] Database Not Initialized")
        return

    # ------------------- Fetch Pending Candidates -------------------
    pending_rows = fetch_pending_candidates(db_conn=db_conn)
    if not pending_rows:
        logging.info("[PENDING][INFO] No pending candidates found. Skipping processing.")
        logging.info("===== PEOPLESTRONG → ERP  Pending END =====")

        return

    logging.info(f"[PENDING] Total pending candidates fetched: {len(pending_rows)}")

    # ------------------- Group Pending Candidates by Mapping File -------------------
    pending_by_mapping = {}
    for row in pending_rows:

        candidate_id, erpid,batch_date, Text_payload, File_Payload, text_done, file_done, erp_done, overall_status, comments, source_file_json, mapping_file = row



        
        mapping_file = str(mapping_file)  # make sure it's a string

        if mapping_file not in pending_by_mapping:
            pending_by_mapping[mapping_file] = []
        pending_by_mapping[mapping_file].append(row)

    # ------------------- Connect SFTP -------------------
    try:
        ssh, sftp = get_sftp_connection()
        logging.info("[PENDING][SFTP] Connection established")
    except Exception as e:
        logging.error(f"[PENDING][SFTP] Connection failed: {e}")
        return

    push_data = []

    # ------------------- Process Each Mapping Batch -------------------
    for mapping_file, candidates in pending_by_mapping.items():
        logging.info(f"[PENDING][Phase 1] Processing batch for mapping file: {mapping_file} ({len(candidates)} candidates)")

        # Extract batch date from mapping_file
        m = re.match(r"Mapping_(\d{8})_\d{6}\.csv", mapping_file)
        if not m:
            logging.warning(f"[PENDING][WARN] Invalid mapping filename format: {mapping_file}")
            continue
        # batch_date = datetime.strptime(m.group(1), "%d%m%Y").date()

        # ------------------- Load Source File List -------------------
        source_file_list = json.loads(candidates[0][9] if candidates[0][9] else "[]")  # FIXED: row[9] is source_file JSON
        if not source_file_list:
            logging.warning(f"[PENDING][WARN] No source files found in DB for mapping {mapping_file}")
            continue

        # ------------------- Load Relevant CSVs -------------------
        dfs = {}
        try:
            for f in source_file_list:
                sftp_path = f"{IMPORT_DIR}/{f}"
                logging.info(f"[PENDING][Phase 2] Loading file {f} → {sftp_path}")
                if "CandidateContact" in f:
                    with sftp.open(sftp_path, "rb") as fh:
                        df = robust_pipe_reader(fh)
                else:
                    with sftp.open(sftp_path, "rb") as fh:
                        df = pd.read_csv(io.BytesIO(fh.read()), sep="|", dtype=str)
                df.columns = df.columns.str.strip()
                dfs[f.split("_")[0]] = df
            logging.info(f"[PENDING][Phase 2] Loaded {len(dfs)} source files for batch {mapping_file}")
        except Exception as e:
            logging.error(f"[PENDING][ERROR] Failed to load source files for mapping {mapping_file}: {e}")
            continue

        # Rename Mapping CSV column for JOIN
        if "Mapping" not in dfs:
            logging.warning(f"[PENDING][WARN] Mapping CSV not found in loaded files for batch {mapping_file}")
            continue
        dfs["Mapping"] = dfs["Mapping"].rename(columns={"PeopleStrongID": JOIN_KEY})

        # ------------------- Build Master DataFrame -------------------
        try:
            master = build_master_dataframe(dfs)
            pending_cids = [row[0] for row in candidates]  # candidate_id
            master = master[master[JOIN_KEY].isin(pending_cids)]
            dump_df(master, f"RPA_Master_File_Pending_{mapping_file}")
            logging.info(f"[PENDING][Phase 3] Master dataframe built for batch {mapping_file} ({len(master)} pending candidates)")
        except Exception as e:
            logging.error(f"[PENDING][ERROR] Failed to build master dataframe for mapping {mapping_file}: {e}")
            continue

        # ------------------- Process Each Candidate -------------------
        for _, r in master.iterrows():
            cid = r[JOIN_KEY]
            erpid = safe(r.get("ERPID"))

            db_row = next((c for c in candidates if c[0] == cid), None)  # lookup by candidate_id
            if db_row:
                _, _, Text_payload, File_Payload, text_done, file_done, erp_done, overall_status, comments, source_file_json, mapping_file = db_row

                
            else:
                Text_payload = File_Payload = None
                text_done = file_done = erp_done = 0
                overall_status = STATUS_PENDING
                comments = None

            logging.info(f"[PENDING][Phase 4] Processing candidate {cid}")

            if not erpid or erpid.upper() == "N/A":
                logging.warning(f"[PENDING][SKIP] ERPID missing for {cid}")
                save_to_queue(
                    candidate_id=cid,
                    erpid="N/A",
                    overall_status=STATUS_FAILED,
                    comments="Missing ERPID — skipped",
                    db_conn=db_conn
                )
                push_data.append({"CandidateID": cid, "ERPID": "N/A", "status": STATUS_FAILED, "comments": "Missing ERPID — skipped"})
                continue

            try:
                if not Text_payload:
                    Text_payload = build_erp_payload(r)
                if not File_Payload:
                    File_Payload = get_candidate_document_links(cid)

                save_to_queue(
                    candidate_id=cid,
                    erpid=erpid,
                    text_payload=json.dumps(Text_payload),
                    db_conn=db_conn,
                    batch_date=batch_date,
                    mapping_file=mapping_file,
                    source_file=json.dumps(source_file_list),
                    text_done=1 if Text_payload else 0,
                    file_done=1 if File_Payload else 0,
                    erp_done=erp_done,
                    overall_status=overall_status
                )
                logging.info(f"[PENDING][Phase 5] Payloads ready for {cid}")
            except Exception as e:
                logging.error(f"[PENDING][ERROR] Payload prep failed for {cid}: {e}")
                save_to_queue(
                    candidate_id=cid,
                    erpid=erpid,
                    overall_status=STATUS_FAILED,
                    comments=f"Payload prep failed: {e}",
                    db_conn=db_conn
                )
                push_data.append({"CandidateID": cid, "ERPID": erpid, "status": STATUS_FAILED, "comments": f"Payload prep failed: {e}"})
                continue

            # ------------------- Push to ERP -------------------
            try:
                if not erp_done:
                    status, resp = send_to_erp(erpid, payload_data=Text_payload, file_data=File_Payload)
                    bot_comment = "Synced Successfully" if status == STATUS_SUCCESS else f"Failed: {resp}"
                    save_to_queue(
                        candidate_id=cid,
                        erpid=erpid,
                        erp_done=1 if status == STATUS_SUCCESS else 0,
                        overall_status=status,
                        comments=bot_comment,
                        db_conn=db_conn
                    )
                    logging.info(f"[PENDING][Phase 6][ERP] Candidate {cid} status={status}")
                else:
                    status = STATUS_SUCCESS
                    bot_comment = "Already Synced"
                    logging.info(f"[PENDING][Phase 6][INFO] Candidate {cid} already synced")
            except Exception as e:
                logging.error(f"[PENDING][ERROR] ERP push failed for {cid}: {e}")
                status = STATUS_FAILED
                bot_comment = f"ERP push exception: {e}"
                save_to_queue(
                    candidate_id=cid,
                    erpid=erpid,
                    overall_status=status,
                    comments=bot_comment,
                    db_conn=db_conn
                )

            push_data.append({"CandidateID": cid, "ERPID": erpid, "status": status, "comments": bot_comment})

    logging.info(f"[PENDING] ===== PENDING PROCESS COMPLETE =====")
    logging.info(f"[PENDING] Total pending candidates processed: {len(push_data)}")



