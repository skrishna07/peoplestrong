

from libraries import *
from modules.Helpers import *
from modules.SEND_EMAIL_SUMMARY import send_pull_summary_email,send_smtp_email
from modules.Sql_Helper import init_db,update_pull_status,fetch_pull_pending_candidates
from api_handler.Ps_to_Erp_Requestor import is_erp_id_valid



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




def ERP_to_PS_Pull(db_conn=None):
    logging.info("=" * 80)
    logging.info("===== ERP → PEOPLESTRONG PULL START =====")
    logging.info(f"Job Started At: {datetime.now()}")

    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0, "pending": 0}
    pull_data = []
    ssh = None

    try:
        # ------------------- Phase 1: Initialize DB -------------------
        try:
            init_db(db_conn=db_conn)
        except Exception as e:
            logging.error("[DB] Database initialization failed: %s", e)

        # ------------------- Phase 2: Connect SFTP -------------------
        logging.info("[PHASE 2] Establishing SFTP connection...")
        ssh, sftp = get_sftp_connection()
        logging.info("[PHASE 2] SFTP connection established successfully.")

        # ------------------- Phase 3: Load Mapping File -------------------
        logging.info("[PHASE 3] Listing mapping files in archive directory '%s'...", ARCHIVE_DIR)
        mapping_files = [f for f in sftp.listdir(ARCHIVE_DIR) if f.startswith('Mapping')]
        if not mapping_files:
            logging.warning("[PHASE 3] No mapping files found. Exiting process.")
            return

        latest_map = sorted(mapping_files, reverse=True)[0]
        logging.info(f"[PHASE 3] Using latest mapping file: {latest_map}")
        with sftp.open(f"{ARCHIVE_DIR}/{latest_map}", "rb") as f:
            df = pd.read_csv(io.BytesIO(f.read()), sep='|', dtype=str)

            # Ensure required headers exist
            if 'ERPID' not in df.columns or 'PeopleStrongID' not in df.columns:
                logging.error("[PHASE 3] Mapping file missing required headers. Exiting process.")
                return

            # Keep only valid ERP IDs (PH…)
            df = df[df['ERPID'].str.startswith('PH')]
            logging.info("[PHASE 3] Mapping file loaded correctly with ERP IDs and PeopleStrong IDs")



        # ------------------- Phase 4: Pending ERP IDs -------------------
        pending_rows = fetch_pull_pending_candidates(db_conn)
        if pending_rows:
            logging.info("[PHASE 4] Resuming pending ERP IDs")
            targets = [row[1] for row in pending_rows if row[1]]
        else:
            targets = df['ERPID'].dropna().unique()
            logging.info(f"[PHASE 4] No pending ERP IDs. Processing live ERP IDs: {targets}")

        stats["total"] = len(targets)
        if stats["total"] == 0:
            logging.warning("[PHASE 4] No ERP IDs to process.")
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

        # ------------------- Phase 5: Process ERP IDs -------------------
        for emp_id in targets:
            logging.info("-" * 60)
            logging.info(f"[PHASE 5] Processing ERP ID: {emp_id}")

            candidate_meta = []

            # Map ERP ID to candidate_id
            candidate_id_row = df.loc[df['ERPID'] == emp_id, 'PeopleStrongID']
            if candidate_id_row.empty:
                logging.warning(f"[SKIP] Candidate ID not found for ERP ID {emp_id}. Skipping.")
                stats["skipped"] += 1
                pull_data.append({
                    "CandidateID": emp_id,
                    "Pull Status": "SKIPPED",
                    "BOT Comments": "Candidate ID not found in mapping",
                    "Data Extracted (files)": ""
                })
                continue
            candidate_id = candidate_id_row.values[0]

            try:
                if not is_erp_id_valid(emp_id):
                    logging.warning(f"[SKIP] ERP ID {emp_id} not generated. Marking as PENDING.")
                    update_pull_status(emp_id, "PENDING", "ERP ID not yet generated", db_conn=db_conn)
                    stats["pending"] += 1
                    pull_data.append({
                        "CandidateID": emp_id,
                        "Pull Status": "PENDING",
                        "BOT Comments": "ERP ID not yet generated",
                        "Data Extracted (files)": ""
                    })
                    continue

                # ------------------- Stage 5a: Fetch Files -------------------
                url = f"{ERP_URL}?employee_ids={emp_id}"
                headers = {'auth': AUTH_TOKEN}
                res = requests.get(url, headers=headers, timeout=30)

                if res.status_code != 200:
                    logging.error(f"[ERROR] API call failed for {emp_id}: {res.status_code}")
                    update_pull_status(emp_id, "FAILED", f"API call failed: {res.status_code}", db_conn=db_conn)
                    stats["failed"] += 1
                    pull_data.append({
                        "CandidateID": emp_id,
                        "Pull Status": "FAILED",
                        "BOT Comments": f"API call failed: {res.status_code}",
                        "Data Extracted (files)": ""
                    })
                    continue

                files = res.json().get("data", {}).get(str(emp_id), {}).get("files", {})
                if not files:
                    logging.info(f"[SKIP] No files found for ERP ID {emp_id}")
                    update_pull_status(emp_id, "SKIPPED", "No files found", db_conn=db_conn)
                    stats["skipped"] += 1
                    pull_data.append({
                        "CandidateID": emp_id,
                        "Pull Status": "SKIPPED",
                        "BOT Comments": "No files found",
                        "Data Extracted (files)": ""
                    })
                    continue

                # ------------------- Stage 5b: Process Files -------------------
                for file_label, file_url in files.items():
                    if file_label not in erp_to_ps_required:
                        stats["skipped"] += 1
                        continue

                    f_name = file_label.split('-')[-1]
                    if '.' not in f_name:
                        f_name += ".pdf"

                    doc_type = filelabel_to_doctype.get(file_label, "UNKNOWN")
                    final_filename = f"{emp_id}_{doc_type}_{f_name}"

                    try:
                        doc_res = requests.get(file_url, timeout=30)
                        doc_res.raise_for_status()
                        if not is_format_valid(f_name):
                            raise Exception("Invalid file format/size")
                        with sftp.open(f"{DOC_DIR}/{final_filename}", "wb") as out_f:
                            out_f.write(doc_res.content)
                    except Exception as e:
                        logging.error(f"[ERROR] File download/validation failed for {emp_id}: {e}")
                        update_pull_status(emp_id, "FAILED", str(e), db_conn=db_conn)
                        stats["failed"] += 1
                        pull_data.append({
                            "CandidateID": emp_id,
                            "Pull Status": "FAILED",
                            "BOT Comments": str(e),
                            "Data Extracted (files)": f_name
                        })
                        continue

                    candidate_meta.append(f"{emp_id}|{DOC_DIR}|{final_filename}|{doc_type}")

                # ------------------- Stage 5c: Write metadata CSV -------------------
                if candidate_meta:
                    meta_filename = f"{INPUT_DIR}/Meta_{emp_id}.csv"
                    with sftp.open(meta_filename, "w") as m_f:
                        m_f.write("EmployeeCode|Path|Filename|DocCode\n")
                        m_f.write("\n".join(candidate_meta))

                update_pull_status(emp_id, "SUCCESS", None, db_conn=db_conn)
                stats["success"] += 1
                pull_data.append({
                    "CandidateID": emp_id,
                    "Pull Status": "SUCCESS",
                    "BOT Comments": "Files synced successfully",
                    "Data Extracted (files)": ", ".join([f.split('|')[2] for f in candidate_meta])
                })

            except Exception as e:
                logging.error(f"[ERROR] Unexpected error processing ERP ID {emp_id}: {e}")
                update_pull_status(emp_id, "FAILED", str(e), db_conn=db_conn)
                stats["failed"] += 1
                pull_data.append({
                    "CandidateID": emp_id,
                    "Pull Status": "FAILED",
                    "BOT Comments": str(e),
                    "Data Extracted (files)": ""
                })

    except Exception as e:
        logging.critical(f"[CRITICAL] System error: {e}")
        logging.error(traceback.format_exc())

    finally:
        if ssh:
            try:
                sftp.close()
                ssh.close()
            except Exception as e:
                logging.error(f"[FINAL] Failed to close SFTP connection: {e}")

        # ------------------- Phase 6: Summary & Emails -------------------
        logging.info("="*80)
        logging.info(f"BATCH SUMMARY → Total: {stats['total']} | Success: {stats['success']} | Pending: {stats['pending']} | Skipped: {stats['skipped']} | Failed: {stats['failed']}")
        print(f"\nBATCH SUMMARY → Total: {stats['total']} | Success: {stats['success']} | Pending: {stats['pending']} | Skipped: {stats['skipped']} | Failed: {stats['failed']}\n")
        logging.info("="*80)

        if stats["success"] > 0:
            send_pull_summary_email(pull_data)
        elif stats["pending"] > 0 or stats["failed"] > 0 or stats["skipped"] > 0:
            non_success_entries = [entry for entry in pull_data if entry["Pull Status"] != "SUCCESS"]
            rows = ""
            for i, entry in enumerate(non_success_entries, start=1):
                rows += f"<tr><td>{i}</td><td>{entry['CandidateID']}</td><td>{entry['Pull Status']}</td><td>{entry['BOT Comments']}</td></tr>"

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

            # send_smtp_email(
            #     subject=f"ERP to  PeopleStrong Pull Pending | {datetime.now().strftime('%d-%m-%Y')}",
            #     html_body=html_body
            # )

        logging.info("===== ERP → PEOPLESTRONG PULL COMPLETE =====")
