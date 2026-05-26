from libraries import *
from modules.Helpers import *
from modules.SEND_EMAIL_SUMMARY import send_pull_summary_email,send_smtp_email
from modules.Sql_Helper import init_db,update_pull_status,fetch_pull_pending_candidates
from modules.Yes_No_Validator import ensure_tracking_files, should_skip_pull, update_pull_tracking, get_completed_pull_docs
from api_handler.Ps_to_Erp_Requestor import is_erp_id_valid,get_erp_numeric_key



Doc_Type = {
    "Person": [
        "EmiratesID-copy",
        "Person-photo",
        "Person-cv",
        "Passport-scan",
        "Person-genericfiles"
    ],
    "SponsorVisa": [
        "SponsorVisa-copy"
    ],
    "SponsorPassport": [
        "SponsorPassport-scan"
    ],
    "EmployeeContract": [
        "EmployeeContract-offerletter",
        "EmployeeContract-codeofconductcopy",
        "EmployeeContract-joiningreportscan",
        "EmployeeContract-personalinfosheet",
        "EmployeeContract-molofferletter",
        "EmployeeContract-cancellationcopy",
        "EmployeeContract-joiningundertaking",
        "EmployeeContract-backgroundcheck",
        "EmployeeContract-sponsornocscan"
    ],
    "EntryVisa": [
        "EntryVisa-visacopy"
    ],
    "PreJoinVisa": [
        "PreJoinVisa-entrystampvisitvisacopy",
        "PreJoinVisa-cancellationpaperscan"
    ],
    "ResidenceVisa": [
        "ResidenceVisa-copy"
    ],
    "ResidenceVisaProcess": [
        "ResidenceVisaProcess-urgentcostapprovalcopy",
        "ResidenceVisaProcess-visastampreceipt"
    ],
    "LaborContract": [
        "LaborContract-laborcardcopy"
    ],
    "LaborContractProcess": [
        "LaborContractProcess-lctypedlaborcontractcopy",
        "LaborContractProcess-signedlabourcontract",
        "LaborContractProcess-lcretypingapproval"
    ],
    "MOLOL": [
        "MOLOL-typedmolofferlcopy",
        "MOLOL-signedmolofferletter",
        "MOLOL-mololclientapproval"
    ],
    "EmpOLProcess": [
        "EmpOLProcess-empexperienceletter",
        "EmpOLProcess-clientauthorizationcopy",
        "EmpOLProcess-referencecheckdocument",
        "EmpOLProcess-referencecheckdocument2",
        "EmpOLProcess-cidclearence"
    ],
    "EmpUAEResidence": [
        "EmpUAEResidence-dewabillcopy",
        "EmpUAEResidence-ejaricert"
    ],
    "EmpCustomization2": [
        "EmpCustomization2-clawbackundertaking",
        "EmpCustomization2-trainingacknowledgement"
    ],
    "IAorTravel": [
        "IAorTravel-iaemployeeundertaking",
        "IAorTravel-iainternalapprovalcopy",
        "IAorTravel-internalamendcashreceipt",
        "IAorTravel-iadocuments"
    ],
    "Insurance": [
        "ILOEInsurance-copy"
    ],
    "MedicalCheck": [
        "MedicalCheck-medicalapplicationcopy",
        "MedicalCheck-medicalstampedapplicationcopy",
        "MedicalCheck-medicalcrtscan",
        "MedicalCheck-medicalreceipt",
        "MedicalCheck-medicalcompletedate"
    ],
    "Qualification": [
        "Qualification-certfile"
    ],
    "EmiratesIDProcess": [
        "EmiratesIDProcess-eidundertaking",
        "EmiratesIDProcess-eidregform",
        "EmiratesIDProcess-eidretyperegform",
        "EmiratesIDProcess-emiratesidoldcopy"
    ]
}










def get_doc_code_from_url(file_url: str) -> str:
    """
    Extracts the DocCode (filelog or _filelog) from an ERP file URL.
    Handles URL-encoded, base64-encoded JSON, with regex fallback.
    """
    try:
        parsed = urllib.parse.urlparse(file_url)
        query_params = urllib.parse.parse_qs(parsed.query)
        q_value = query_params.get('q', [])
        if not q_value:
            return ""

        # URL-decode and split at '|'
        encoded_str = urllib.parse.unquote(q_value[0]).split('|')[0]

        # Base64-decode
        try:
            missing_padding = len(encoded_str) % 4
            if missing_padding:
                encoded_str += "=" * (4 - missing_padding)
            decoded_bytes = base64.b64decode(encoded_str)
            decoded_str = decoded_bytes.decode('utf-8')
        except Exception:
            decoded_str = encoded_str  # fallback

        # JSON parsing
        try:
            data = json.loads(decoded_str)
            doc_code = data.get('_filelog') or data.get('filelog')
            if doc_code:
                return str(doc_code)
        except json.JSONDecodeError:
            pass

        # Regex fallback
        match = re.search(r'\d{6,}', decoded_str)
        if match:
            return match.group(0)

        # Last resort
        match_url = re.search(r'\d{6,}', file_url)
        if match_url:
            return match_url.group(0)

    except Exception:
        return ""

    return ""





filelabel_to_doctype = {f: dt for dt, files in Doc_Type.items() for f in files}

# Only the 5 required documents including Joining MOL
erp_to_ps_required = {
    "ILOEInsurance-copy": "Joining–Insurance_Card",
    "LaborContract-laborcardcopy": "Joining–Labour_Card",
    "MOLOL-typedmolofferlcopy": "Joining–MOL_Document",
    "EmiratesID-copy": "Post_Joining–Typed_Emirates_Copy",
    "ResidenceVisaProcess-visastampreceipt": "Post_Joining–Stamped_Visa"
    
    
}




def ERP_to_PS_Pull(db_conn=None, max_ids=None):
    logging.info("=" * 80)
    logging.info("===== ERP → PEOPLESTRONG PULL START =====")
    logging.info(f"Job Started At: {datetime.now()}")

    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "pending": 0}
    pull_data = []
    ssh = None
    sftp = None
    latest_map = ""
    batch_date_value = ""

    try:
        try:
            init_db(db_conn=db_conn)
            ensure_tracking_files()
        except Exception as e:
            logging.error("[DB] Database initialization failed: %s", e)

        logging.info("[PHASE 2] Establishing SFTP connection...")
        ssh, sftp = get_sftp_connection()
        logging.info("[PHASE 2] SFTP connection established successfully.")

        logging.info("[PHASE 3] Listing mapping files in archive directory '%s'...", ARCHIVE_DIR)
        mapping_files = [f for f in sftp.listdir(ARCHIVE_DIR) if f.startswith('Mapping')]
        if not mapping_files:
            logging.warning("[PHASE 3] No mapping files found. Exiting process.")
            return

        def _mapping_file_dt(file_name: str):
            match = re.match(r"Mapping_(\d{8})_(\d{6})\.csv$", str(file_name).strip(), re.IGNORECASE)
            if not match:
                return None
            try:
                return datetime.strptime(f"{match.group(1)}{match.group(2)}", "%d%m%Y%H%M%S")
            except Exception:
                return None

        parsed_mapping_files = [(f, _mapping_file_dt(f)) for f in mapping_files]
        valid_mapping_files = [item for item in parsed_mapping_files if item[1] is not None]
        if valid_mapping_files:
            latest_map = max(valid_mapping_files, key=lambda x: x[1])[0]
        else:
            latest_map = sorted(mapping_files, reverse=True)[0]
        map_match = re.search(r"Mapping_(\d{8})_", latest_map)
        if map_match:
            batch_date_value = datetime.strptime(map_match.group(1), "%d%m%Y").date().isoformat()
        logging.info(f"[PHASE 3] Using latest mapping file: {latest_map}")

        with sftp.open(f"{ARCHIVE_DIR}/{latest_map}", "rb") as file_obj:
            df = pd.read_csv(io.BytesIO(file_obj.read()), sep='|', dtype=str)

        if 'ERPID' not in df.columns or 'PeopleStrongID' not in df.columns:
            logging.error("[PHASE 3] Mapping file missing required headers. Exiting process.")
            return

        # Normalize ERP IDs to avoid false negatives caused by spaces/case/missing values.
        df['ERPID'] = df['ERPID'].fillna('').astype(str).str.strip()
        df = df[df['ERPID'].str.upper().str.startswith('PH')]
        logging.info("[PHASE 3] Mapping file loaded correctly with ERP IDs and PeopleStrong IDs")

        pending_rows = fetch_pull_pending_candidates(db_conn)
        pending_targets = []
        if pending_rows:
            logging.info("[PHASE 4] Resuming pending ERP IDs")
            pending_targets = [
                str(row[1]).strip()
                for row in pending_rows
                if row[1] and str(row[1]).strip() and str(row[1]).strip().upper() not in ('N/A', 'NA', 'NONE', 'NULL')
            ]
            logging.info("[PHASE 4] Valid pending ERP ID(s): %d", len(pending_targets))

        mapping_targets = [
            target_id.strip()
            for target_id in df['ERPID'].dropna().astype(str).tolist()
            if target_id.strip() and target_id.strip().upper() not in ('N/A', 'NA', 'NONE', 'NULL')
        ]
        logging.info("[PHASE 4] Valid mapping ERP ID(s): %d", len(mapping_targets))

        # Process pending first, then include remaining IDs from latest mapping file.
        targets = []
        seen = set()
        for target_list in (pending_targets, mapping_targets):
            for target_id in target_list:
                norm_id = target_id.upper()
                if norm_id in seen:
                    continue
                seen.add(norm_id)
                targets.append(target_id)

        logging.info("[PHASE 4] Total unique ERP ID(s) to process: %d", len(targets))

        if isinstance(max_ids, int) and max_ids > 0:
            targets = targets[:max_ids]
            logging.info(f"[LIMIT] Pull processing limited to first {len(targets)} ERP ID(s).")

        stats["total"] = len(targets)
        if stats["total"] == 0:
            logging.warning("[PHASE 4] No valid ERP IDs to process.")
            send_smtp_email(
                subject=f"ERP to PeopleStrong Pull | No Candidates | {datetime.now().strftime('%d-%m-%Y')}",
                html_body=f"""
                <html>
                <body>
                    <p>Dear Team,</p>
                    <p>The latest mapping file <b>{latest_map}</b> contains no valid ERP IDs to process.</p>
                    <p>No files were pulled in this run.</p>
                    <p>Regards,<br><b>RPA BOT</b></p>
                </body>
                </html>
                """
            )
            return

        for emp_id in targets:
            logging.info("-" * 60)
            logging.info(f"[PHASE 5] Processing ERP ID: {emp_id}")

            docs_info = get_completed_pull_docs(emp_id)
            missing_required_docs = [label for label in erp_to_ps_required.keys() if label not in docs_info]

            if should_skip_pull(emp_id, latest_map):
                logging.info(f"[SKIP] ERP ID {emp_id} already completed for mapping file {latest_map}. Skipping duplicate pull.")
                stats["skipped"] += 1
                pull_data.append({
                    "CandidateID": emp_id,
                    "Pull Status": "SKIPPED",
                    "BOT Comments": "Already pulled for same mapping file",
                    "Data Extracted (files)": ""
                })
                continue

            try:
                emp_numeric = get_erp_numeric_key(emp_id)

                if not is_erp_id_valid(emp_id):
                    logging.warning(f"[PENDING] ERP ID {emp_numeric} not generated yet. Marking as pending.")
                    update_pull_status(emp_id, "PENDING", "ERP ID not yet generated", db_conn=db_conn)
                    update_pull_tracking(
                        candidate_id=emp_id,
                        employee_code=emp_id,
                        erp_valid=False,
                        text_data_pulled=False,
                        docs_info=docs_info,
                        missing_docs=missing_required_docs,
                        mapping_file=latest_map,
                        batch_date=batch_date_value,
                        final_status="PENDING",
                        pull_status="PENDING",
                        db_overall_status="PENDING",
                        db_pull_status="PENDING",
                        db_text_done=0,
                        db_file_done=0,
                        db_erp_done=0,
                        id_text_data="No",
                        comments="ERP ID not yet generated",
                        db_comments="ERP ID not yet generated"
                    )
                    stats["pending"] += 1
                    pull_data.append({
                        "CandidateID": emp_id,
                        "Pull Status": "PENDING",
                        "BOT Comments": "ERP ID not yet generated",
                        "Data Extracted (files)": ""
                    })
                    continue

                url = f"{ERP_URL}?employee_ids={emp_numeric}"
                headers = {'auth': AUTH_TOKEN}
                response = requests.get(url, headers=headers, timeout=30)
                if response.status_code != 200:
                    raise Exception(f"API call failed: {response.status_code}")

                files = response.json().get("data", {}).get(str(emp_numeric), {}).get("files", {})
                if not files:
                    logging.info(f"[SKIP] No files found for ERP ID {emp_id}")
                    update_pull_status(emp_id, "SKIPPED", "No files found", db_conn=db_conn)
                    update_pull_tracking(
                        candidate_id=emp_id,
                        employee_code=emp_id,
                        erp_valid=True,
                        text_data_pulled=False,
                        docs_info=docs_info,
                        missing_docs=missing_required_docs,
                        mapping_file=latest_map,
                        batch_date=batch_date_value,
                        final_status="SKIPPED",
                        pull_status="SKIPPED",
                        db_overall_status="PENDING",
                        db_pull_status="SKIPPED",
                        db_text_done=0,
                        db_file_done=0,
                        db_erp_done=0,
                        id_text_data="No",
                        comments="No files found",
                        db_comments="No files found"
                    )
                    stats["skipped"] += 1
                    pull_data.append({
                        "CandidateID": emp_id,
                        "Pull Status": "SKIPPED",
                        "BOT Comments": "No files found",
                        "Data Extracted (files)": ""
                    })
                    continue

                all_candidate_meta = []
                emp_folder = f"{DOC_DIR}/{emp_id}"
                try:
                    sftp.stat(emp_folder)
                except IOError:
                    sftp.mkdir(emp_folder)

                for file_label, file_url in files.items():
                    if file_label not in erp_to_ps_required:
                        continue
                    if file_label in docs_info:
                        logging.info(f"[SKIP] {emp_id} | {file_label} already completed. Skipping one-time document reprocessing.")
                        continue

                    file_name = file_label.split('-')[-1]
                    if '.' not in file_name:
                        file_name += ".pdf"

                    if not is_format_valid(file_name):
                        logging.warning(f"[SKIP] Invalid file format/size for {emp_id} | {file_label}")
                        continue

                    doc_type = filelabel_to_doctype.get(file_label, "UNKNOWN")
                    final_filename = f"{emp_id}_{doc_type}_{file_name}"

                    doc_response = requests.get(file_url, timeout=30)
                    doc_response.raise_for_status()
                    with sftp.open(f"{emp_folder}/{final_filename}", "wb") as out_file:
                        out_file.write(doc_response.content)

                    docs_info[file_label] = {
                        "filename": final_filename,
                        "path": f"{emp_folder}/{final_filename}",
                        "url": file_url
                    }
                    all_candidate_meta.append(f"{emp_id}|{emp_folder}|{final_filename}|{doc_type}")

                if all_candidate_meta:
                    meta_filename = f"{INPUT_DIR}/Meta_{emp_id}.csv"
                    with sftp.open(meta_filename, "w") as meta_file:
                        meta_file.write("EmployeeCode|Path|Filename|DocCode\n")
                        meta_file.write("\n".join(all_candidate_meta))

                missing_required_docs = [label for label in erp_to_ps_required.keys() if label not in docs_info]
                update_pull_status(emp_id, "SUCCESS", None, db_conn=db_conn)
                update_pull_tracking(
                    candidate_id=emp_id,
                    employee_code=emp_id,
                    erp_valid=True,
                    text_data_pulled=False,
                    docs_info=docs_info,
                    missing_docs=missing_required_docs,
                    mapping_file=latest_map,
                    batch_date=batch_date_value,
                    final_status="SUCCESS",
                    pull_status="SUCCESS",
                    db_overall_status="PENDING",
                    db_pull_status="SUCCESS",
                    db_text_done=0,
                    db_file_done=1 if docs_info else 0,
                    db_erp_done=0,
                    id_text_data="No",
                    comments="Files synced successfully",
                    db_comments="Files synced successfully"
                )
                stats["success"] += 1
                pull_data.append({
                    "CandidateID": emp_id,
                    "Pull Status": "SUCCESS",
                    "BOT Comments": "Files synced successfully",
                    "Data Extracted (files)": ", ".join([meta.split('|')[2] for meta in all_candidate_meta])
                })

            except Exception as e:
                err_str = str(e)
                logging.error(f"[ERROR] Failed to process ERP ID {emp_id}: {err_str}")

                # SFTP socket closed mid-run — reconnect and retry this ID once
                if "socket is closed" in err_str.lower() or "ssh session not active" in err_str.lower():
                    logging.warning("[SFTP] Socket closed during processing. Attempting reconnect...")
                    try:
                        try:
                            sftp.close()
                        except Exception:
                            pass
                        try:
                            ssh.close()
                        except Exception:
                            pass
                        ssh, sftp = get_sftp_connection()
                        logging.info("[SFTP] Reconnected. Retrying ERP ID %s", emp_id)
                        # Re-raise so the outer loop naturally retries on next run
                        # (don't retry inline to avoid silent double-processing)
                    except Exception as reconnect_err:
                        logging.error("[SFTP] Reconnect failed: %s", reconnect_err)

                update_pull_status(emp_id, "FAILED", err_str, db_conn=db_conn)
                stats["failed"] += 1
                pull_data.append({
                    "CandidateID": emp_id,
                    "Pull Status": "FAILED",
                    "BOT Comments": err_str,
                    "Data Extracted (files)": ""
                })

    except Exception as e:
        logging.error(f"[FATAL] ERP pull job failed: {e}")
    finally:
        if sftp:
            sftp.close()
        if ssh:
            ssh.close()

    logging.info("=" * 80)
    logging.info(
        f"BATCH SUMMARY → Total: {stats['total']} | Success: {stats['success']} | "
        f"Pending: {stats['pending']} | Skipped: {stats['skipped']} | Failed: {stats['failed']}"
    )
    logging.info(f"Detailed pull info: {pull_data}")

    if stats["success"] > 0:
        send_pull_summary_email(pull_data)
    elif stats["pending"] > 0 or stats["failed"] > 0 or stats["skipped"] > 0:
        non_success_entries = [entry for entry in pull_data if entry["Pull Status"] != "SUCCESS"]
        rows = ""
        for index, entry in enumerate(non_success_entries, start=1):
            rows += (
                f"<tr><td>{index}</td><td>{entry['CandidateID']}</td>"
                f"<td>{entry['Pull Status']}</td><td>{entry['BOT Comments']}</td></tr>"
            )

        html_body = f"""
        <html>
        <body style="font-family:Calibri, sans-serif; font-size:14px;">
            <p>Dear Team,</p>
            <p>The following ERP IDs could not be successfully processed and will be reviewed in the next run. Once generated in ERP, the process will automatically resume:</p>
            <table border="1" cellpadding="6" cellspacing="0" style="border-collapse:collapse; width:60%;">
                <tr style="background-color:#d9e1f2;">
                    <th>S.No</th>
                    <th>ERP ID</th>
                    <th>Status</th>
                    <th>Comments</th>
                </tr>
                {rows}
            </table>
            <p>Regards,<br><b>RPA BOT</b></p>
        </body>
        </html>
        """
        send_smtp_email(
            subject=f"ERP to PeopleStrong Pull Pending | {datetime.now().strftime('%d-%m-%Y')}",
            html_body=html_body
        )

    logging.info("===== ERP → PEOPLESTRONG PULL COMPLETE =====")
