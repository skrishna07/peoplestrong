

from libraries import *
from modules.Helpers import *
from modules.SEND_EMAIL_SUMMARY import send_pull_summary_email,send_smtp_email
from modules.Sql_Helper import init_db,update_pull_status



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


filelabel_to_doctype = {f: dt for dt, files in Doc_Type.items() for f in files}


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





# def ERP_to_PS_Pull():
#     logging.info("="*60)
#     logging.info("PROCESS START: ERP TO PEOPLESTRONG DOCUMENT SYNC")
#     stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
#     ssh = None
#     pull_data = []

#     try:
#         logging.info("Step 1: Establishing SFTP connection...")
#         ssh, sftp = get_sftp_connection()
#         logging.info("SFTP connection established successfully.")

#         logging.info("Step 2: Listing mapping files in archive directory '%s'...", ARCHIVE_DIR)
#         mapping_files = [f for f in sftp.listdir(ARCHIVE_DIR) if f.startswith('Mapping')]
#         logging.info("Found %d mapping file(s): %s", len(mapping_files), mapping_files)

#         if not mapping_files:
#             logging.warning("No mapping files found. Exiting process.")
#             return

#         latest_map = sorted(mapping_files, reverse=True)[0]
#         logging.info("Step 3: Using latest mapping file: %s", latest_map)

#         with sftp.open(f"{ARCHIVE_DIR}/{latest_map}", "rb") as f:
#             df = pd.read_csv(io.BytesIO(f.read()), sep='|', dtype=str)

#             if 'ERPID' in df.columns and 'PeopleStrongID' in df.columns:
#                 if df['ERPID'].str.startswith('PH').any():
#                     df = df.rename(columns={'ERPID':'PeopleStrongID', 'PeopleStrongID':'ERPID'})
#                     logging.info("Columns swapped to match ERPID|PeopleStrongID format")
#             else:
#                 logging.error("Mapping file missing required headers 'ERPID' or 'PeopleStrongID'")
#                 return

#             invalid_ps_ids = df[~df['PeopleStrongID'].str.startswith('PH')]
#             if not invalid_ps_ids.empty:
#                 logging.warning("Some PeopleStrong IDs are invalid and will be skipped: %s", invalid_ps_ids)
#                 df = df[df['PeopleStrongID'].str.startswith('PH')]

#             targets = df['ERPID'].dropna().unique()
#             stats["total"] = len(targets)
#             logging.info("Step 4: Extracted %d valid ERP IDs to process: %s", len(targets), targets)

#             if len(targets) == 0:
#                 logging.warning(f"No valid ERP IDs found in mapping file: {latest_map}")
#                 send_smtp_email(
#                     subject=f"ERP to  PeopleStrong Pull | No Candidates | {datetime.now().strftime('%d-%m-%Y')}",
#                     html_body=f"""
#                     <html>
#                     <body>
#                         <p>Dear Team,</p>
#                         <p>The latest mapping file <b>{latest_map}</b> contains <b>no valid ERP IDs</b> to process.</p>
#                         <p>No files were pulled in this run.</p>
#                         <p>Regards,<br><b>RPA BOT</b></p>
#                     </body>
#                     </html>
#                     """
#                 )
#                 return
                

#         for emp_id in targets:
#             logging.info("-"*30)
#             logging.info("Step 5: Processing ERP ID: %s", emp_id)
#             candidate_meta = []

#             try:
#                 url = f"{ERP_URL}?employee_ids={emp_id}"
#                 headers = {'auth': AUTH_TOKEN}
#                 logging.info("Calling ERP API: %s", url)
#                 res = requests.get(url, headers=headers, timeout=30)
#                 logging.info("Received API response: Status Code=%d", res.status_code)

#                 if res.status_code != 200:
#                     logging.error("API call failed for %s: Status %d", emp_id, res.status_code)
#                     stats["failed"] += 1
#                     update_pull_status(emp_id, "FAILED", f"API call failed: Status {res.status_code}")
#                     pull_data.append({"Candidate ID": emp_id, "Data Extracted (files)": "", "Pull Status": "FAILED",
#                                       "BOT Comments": f"API call failed: Status {res.status_code}"})
#                     continue

#                 response_json = res.json()
#                 data = response_json.get("data", {}).get(str(emp_id), {}).get("files", {})
#                 logging.info("Step 6: Retrieved file info: %s", data)

#                 if not data:
#                     logging.info("No files found for ERP ID %s. Skipping.", emp_id)
#                     stats["skipped"] += 1
#                     update_pull_status(emp_id, "FAILED", "No files found")
#                     pull_data.append({"Candidate ID": emp_id, "Data Extracted (files)": "", "Pull Status": "SKIPPED",
#                                       "BOT Comments": "No files found"})
#                     continue

#                 for file_label, file_url in data.items():
#                     f_name = file_label.split('-')[-1]
#                     if "." not in f_name:
#                         f_name += ".pdf"

#                     doc_type = filelabel_to_doctype.get(file_label, "Unknown")
#                     final_filename = f"{emp_id}_{doc_type}_{f_name}"

#                     logging.info("Step 7: Downloading file '%s' from URL: %s", f_name, file_url)
#                     try:
#                         doc_res = requests.get(file_url, timeout=30)
#                         doc_res.raise_for_status()
#                         logging.info("File '%s' downloaded successfully.", f_name)
#                     except Exception as e:
#                         logging.error("Failed to download '%s': %s", f_name, str(e))
#                         stats["failed"] += 1
#                         update_pull_status(emp_id, "FAILED", str(e))
#                         pull_data.append({"Candidate ID": emp_id, "Data Extracted (files)": f_name,
#                                           "Pull Status": "FAILED", "BOT Comments": str(e)})
#                         continue

#                     logging.info("Step 8: Validating file '%s'", f_name)
#                     if not is_format_valid(f_name):
#                         logging.warning("Skipped file '%s': Invalid format or size", f_name)
#                         stats["skipped"] += 1
#                         update_pull_status(emp_id, "FAILED", "Invalid format or size")
#                         pull_data.append({"Candidate ID": emp_id, "Data Extracted (files)": f_name,
#                                           "Pull Status": "SKIPPED", "BOT Comments": "Invalid format or size"})
#                         continue

#                     logging.info("Step 9: Writing file to SFTP '%s/%s'", DOC_DIR, final_filename)
#                     with sftp.open(f"{DOC_DIR}/{final_filename}", "wb") as out_f:
#                         out_f.write(doc_res.content)

#                     ps_id = df.loc[df['ERPID'] == emp_id, 'PeopleStrongID'].values[0]
#                     doc_code = get_doc_code_from_url(file_url) or "UNKNOWN"
#                     candidate_meta.append(f"{ps_id}|{DOC_DIR}|{final_filename}|{doc_type}")

#                     stats["success"] += 1
#                     update_pull_status(emp_id, "SUCCESS")
#                     pull_data.append({"Candidate ID": emp_id, "Data Extracted (files)": final_filename,
#                                       "Pull Status": "SUCCESS", "BOT Comments": "File synced successfully"})

#                 # Write metadata CSV
#                 if candidate_meta:
#                     meta_filename = f"{INPUT_DIR}/Meta_{emp_id}.csv"
#                     logging.info("Writing single metadata CSV for candidate: %s", meta_filename)
#                     with sftp.open(meta_filename, "w") as m_f:
#                         m_f.write("EmployeeCode|Path|Filename|DocCode\n")
#                         m_f.write("\n".join(candidate_meta))

#             except Exception as e:
#                 logging.error("Error processing ERP ID %s: %s", emp_id, str(e))
#                 stats["failed"] += 1
#                 update_pull_status(emp_id, "FAILED", str(e))
#                 pull_data.append({"Candidate ID": emp_id, "Data Extracted (files)": "", "Pull Status": "FAILED",
#                                   "BOT Comments": str(e)})

#     except Exception as e:
#         logging.critical("CRITICAL SYSTEM ERROR: %s", str(e))
#         logging.error(traceback.format_exc())

#     finally:
#         if ssh:
#             ssh.close()
#             logging.info("SFTP Connection closed safely.")

#         logging.info("PROCESS SUMMARY: Total=%d, Success=%d, Failed=%d, Skipped=%d",
#                      stats["total"], stats["success"], stats["failed"], stats["skipped"])
#         logging.info("PROCESS END")
#         logging.info("="*60)

#         try:
#             logging.info("Step 11: Sending pull summary email...")
#             send_pull_summary_email(pull_data)
#             logging.info("Pull summary email sent successfully.")
#         except Exception as e:
#             logging.error("Failed to send pull summary email: %s", str(e))





def ERP_to_PS_Pull():
    logging.info("="*60)
    logging.info("PROCESS START: ERP TO PEOPLESTRONG DOCUMENT SYNC")
    stats = {"total": 0, "success": 0, "failed": 0, "skipped": 0}
    ssh = None
    pull_data = []

    try:
        logging.info("Step 1: Establishing SFTP connection...")
        ssh, sftp = get_sftp_connection()
        logging.info("SFTP connection established successfully.")

        logging.info("Step 2: Listing mapping files in archive directory '%s'...", ARCHIVE_DIR)
        mapping_files = [f for f in sftp.listdir(ARCHIVE_DIR) if f.startswith('Mapping')]
        logging.info("Found %d mapping file(s): %s", len(mapping_files), mapping_files)

        if not mapping_files:
            logging.warning("No mapping files found. Exiting process.")
            return

        latest_map = sorted(mapping_files, reverse=True)[0]
        logging.info("Step 3: Using latest mapping file: %s", latest_map)

        with sftp.open(f"{ARCHIVE_DIR}/{latest_map}", "rb") as f:
            df = pd.read_csv(io.BytesIO(f.read()), sep='|', dtype=str)

            if 'ERPID' in df.columns and 'PeopleStrongID' in df.columns:
                if df['ERPID'].str.startswith('PH').any():
                    df = df.rename(columns={'ERPID':'PeopleStrongID', 'PeopleStrongID':'ERPID'})
                    logging.info("Columns swapped to match ERPID|PeopleStrongID format")
            else:
                logging.error("Mapping file missing required headers 'ERPID' or 'PeopleStrongID'")
                return

            invalid_ps_ids = df[~df['PeopleStrongID'].str.startswith('PH')]
            if not invalid_ps_ids.empty:
                logging.warning("Some PeopleStrong IDs are invalid and will be skipped: %s", invalid_ps_ids)
                df = df[df['PeopleStrongID'].str.startswith('PH')]

            targets = df['ERPID'].dropna().unique()
            stats["total"] = len(targets)
            logging.info("Step 4: Extracted %d valid ERP IDs to process: %s", len(targets), targets)

        # If no ERP IDs, send one email and exit
        if len(targets) == 0:
            logging.warning(f"No valid ERP IDs found in mapping file: {latest_map}")
            try:
                send_smtp_email(
                    subject=f"ERP to PeopleStrong Pull | No Candidates | {datetime.now().strftime('%d-%m-%Y')}",
                    html_body=f"""
                    <html>
                    <body>
                        <p>Dear Team,</p>
                        <p>The latest mapping file <b>{latest_map}</b> contains <b>no valid ERP IDs</b> to process.</p>
                        <p>No files were pulled in this run.</p>
                        <p>Regards,<br><b>RPA BOT</b></p>
                    </body>
                    </html>
                    """
                )
            except Exception as e:
                logging.error("Failed to send 'No Candidates' email: %s", str(e))
            return

        # Process each ERP ID
        for emp_id in targets:
            logging.info("-"*30)
            logging.info("Step 5: Processing ERP ID: %s", emp_id)
            candidate_meta = []

            try:
                url = f"{ERP_URL}?employee_ids={emp_id}"
                headers = {'auth': AUTH_TOKEN}
                logging.info("Calling ERP API: %s", url)
                res = requests.get(url, headers=headers, timeout=30)
                logging.info("Received API response: Status Code=%d", res.status_code)

                if res.status_code != 200:
                    logging.error("API call failed for %s: Status %d", emp_id, res.status_code)
                    stats["failed"] += 1
                    update_pull_status(emp_id, "FAILED", f"API call failed: Status {res.status_code}")
                    pull_data.append({
                        "Candidate ID": emp_id, "Data Extracted (files)": "",
                        "Pull Status": "FAILED", "BOT Comments": f"API call failed: Status {res.status_code}"
                    })
                    continue

                response_json = res.json()
                data = response_json.get("data", {}).get(str(emp_id), {}).get("files", {})
                logging.info("Step 6: Retrieved file info: %s", data)

                if not data:
                    logging.info("No files found for ERP ID %s. Skipping.", emp_id)
                    stats["skipped"] += 1
                    update_pull_status(emp_id, "FAILED", "No files found")
                    pull_data.append({
                        "Candidate ID": emp_id, "Data Extracted (files)": "",
                        "Pull Status": "SKIPPED", "BOT Comments": "No files found"
                    })
                    continue

                for file_label, file_url in data.items():
                    f_name = file_label.split('-')[-1]
                    if "." not in f_name:
                        f_name += ".pdf"

                    doc_type = filelabel_to_doctype.get(file_label, "Unknown")
                    final_filename = f"{emp_id}_{doc_type}_{f_name}"

                    logging.info("Step 7: Downloading file '%s' from URL: %s", f_name, file_url)
                    try:
                        doc_res = requests.get(file_url, timeout=30)
                        doc_res.raise_for_status()
                        logging.info("File '%s' downloaded successfully.", f_name)
                    except Exception as e:
                        logging.error("Failed to download '%s': %s", f_name, str(e))
                        stats["failed"] += 1
                        update_pull_status(emp_id, "FAILED", str(e))
                        pull_data.append({
                            "Candidate ID": emp_id, "Data Extracted (files)": f_name,
                            "Pull Status": "FAILED", "BOT Comments": str(e)
                        })
                        continue

                    logging.info("Step 8: Validating file '%s'", f_name)
                    if not is_format_valid(f_name):
                        logging.warning("Skipped file '%s': Invalid format or size", f_name)
                        stats["skipped"] += 1
                        update_pull_status(emp_id, "FAILED", "Invalid format or size")
                        pull_data.append({
                            "Candidate ID": emp_id, "Data Extracted (files)": f_name,
                            "Pull Status": "SKIPPED", "BOT Comments": "Invalid format or size"
                        })
                        continue

                    logging.info("Step 9: Writing file to SFTP '%s/%s'", DOC_DIR, final_filename)
                    with sftp.open(f"{DOC_DIR}/{final_filename}", "wb") as out_f:
                        out_f.write(doc_res.content)

                    ps_id = df.loc[df['ERPID'] == emp_id, 'PeopleStrongID'].values[0]
                    doc_code = get_doc_code_from_url(file_url) or "UNKNOWN"
                    candidate_meta.append(f"{ps_id}|{DOC_DIR}|{final_filename}|{doc_type}")

                    stats["success"] += 1
                    update_pull_status(emp_id, "SUCCESS")
                    pull_data.append({
                        "Candidate ID": emp_id, "Data Extracted (files)": final_filename,
                        "Pull Status": "SUCCESS", "BOT Comments": "File synced successfully"
                    })

                # Write metadata CSV
                if candidate_meta:
                    meta_filename = f"{INPUT_DIR}/Meta_{emp_id}.csv"
                    logging.info("Writing single metadata CSV for candidate: %s", meta_filename)
                    with sftp.open(meta_filename, "w") as m_f:
                        m_f.write("EmployeeCode|Path|Filename|DocCode\n")
                        m_f.write("\n".join(candidate_meta))

            except Exception as e:
                logging.error("Error processing ERP ID %s: %s", emp_id, str(e))
                stats["failed"] += 1
                update_pull_status(emp_id, "FAILED", str(e))
                pull_data.append({
                    "Candidate ID": emp_id, "Data Extracted (files)": "",
                    "Pull Status": "FAILED", "BOT Comments": str(e)
                })

    except Exception as e:
        logging.critical("CRITICAL SYSTEM ERROR: %s", str(e))
        logging.error(traceback.format_exc())

    finally:
        if ssh:
            ssh.close()
            logging.info("SFTP Connection closed safely.")

        logging.info("PROCESS SUMMARY: Total=%d, Success=%d, Failed=%d, Skipped=%d",
                     stats["total"], stats["success"], stats["failed"], stats["skipped"])
        logging.info("PROCESS END")
        logging.info("="*60)

        # Send only one summary email for all processed ERP IDs
        if stats["total"] > 0:
            try:
                logging.info("Step 11: Sending pull summary email...")
                send_pull_summary_email(pull_data)
                logging.info("Pull summary email sent successfully.")
            except Exception as e:
                logging.error("Failed to send pull summary email: %s", str(e))
