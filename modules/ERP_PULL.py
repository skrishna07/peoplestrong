from libraries import *
from modules.Helpers import *
from modules.SEND_EMAIL_SUMMARY import send_pull_summary_email

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
            targets = df['ERPID'].dropna().unique()
            stats["total"] = len(targets)
            logging.info("Step 4: Extracted %d unique ERP IDs to process: %s", len(targets), targets)

        for emp_id in targets:
            logging.info("-"*30)
            logging.info("Step 5: Processing ERP ID: %s", emp_id)

            try:
                url = f"{ERP_URL}?employee_ids={emp_id}"
                headers = {'auth': AUTH_TOKEN}
                logging.info("Calling ERP API: %s", url)
                res = requests.get(url, headers=headers, timeout=30)
                logging.info("Received API response: Status Code=%d", res.status_code)

                if res.status_code != 200:
                    logging.error("API call failed for %s: Status %d", emp_id, res.status_code)
                    stats["failed"] += 1
                    pull_data.append({
                        "Candidate ID": emp_id,
                        "Data Extracted (files)": "",
                        "Pull Status": "FAILED",
                        "BOT Comments": f"API call failed: Status {res.status_code}"
                    })
                    continue

                response_json = res.json()
                data = response_json.get("data", {}).get(str(emp_id), {}).get("files", {})
                logging.info("Step 6: Retrieved file info: %s", data)

                if not data:
                    logging.info("No files found for ERP ID %s. Skipping.", emp_id)
                    stats["skipped"] += 1
                    pull_data.append({
                        "Candidate ID": emp_id,
                        "Data Extracted (files)": "",
                        "Pull Status": "SKIPPED",
                        "BOT Comments": "No files found"
                    })
                    continue

                for file_label, file_url in data.items():
                    f_name = file_label.split('-')[-1]
                    if "." not in f_name:
                        f_name += ".pdf"

                    logging.info("Step 7: Downloading file '%s' from URL: %s", f_name, file_url)
                    try:
                        doc_res = requests.get(file_url, timeout=30)
                        doc_res.raise_for_status()
                        logging.info("File '%s' downloaded successfully.", f_name)
                    except Exception as e:
                        logging.error("Failed to download '%s': %s", f_name, str(e))
                        stats["failed"] += 1
                        pull_data.append({
                            "Candidate ID": emp_id,
                            "Data Extracted (files)": f_name,
                            "Pull Status": "FAILED",
                            "BOT Comments": str(e)
                        })
                        continue

                    logging.info("Step 8: Validating file '%s'", f_name)
                    if not is_format_valid(f_name) or not is_size_valid(doc_res.content, f_name):
                        logging.warning("Skipped file '%s': Invalid format or size", f_name)
                        stats["skipped"] += 1
                        pull_data.append({
                            "Candidate ID": emp_id,
                            "Data Extracted (files)": f_name,
                            "Pull Status": "SKIPPED",
                            "BOT Comments": "Invalid format or size"
                        })
                        continue

                    final_filename = f"{emp_id}_LabourCard_{f_name}"
                    logging.info("Step 9: Writing file to SFTP '%s/%s'", DOC_DIR, final_filename)
                    with sftp.open(f"{DOC_DIR}/{final_filename}", "wb") as out_f:
                        out_f.write(doc_res.content)

                    meta_content = f"Candidate ID|Path|Filename|DocCode\n{emp_id}|{DOC_DIR}|{final_filename}|Labour Card"
                    logging.info("Step 10: Writing metadata file to SFTP '%s/Meta_%s.csv'", INPUT_DIR, final_filename)
                    with sftp.open(f"{INPUT_DIR}/Meta_{final_filename}.csv", "w") as m_f:
                        m_f.write(meta_content)

                    stats["success"] += 1
                    pull_data.append({
                        "Candidate ID": emp_id,
                        "Data Extracted (files)": final_filename,
                        "Pull Status": "SUCCESS",
                        "BOT Comments": "File synced successfully"
                    })

            except Exception as e:
                logging.error("Error processing ERP ID %s: %s", emp_id, str(e))
                stats["failed"] += 1
                pull_data.append({
                    "Candidate ID": emp_id,
                    "Data Extracted (files)": "",
                    "Pull Status": "FAILED",
                    "BOT Comments": str(e)
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

        # Step 11: Send Pull Summary Email
        try:
            logging.info("Step 11: Sending pull summary email...")
            send_pull_summary_email(pull_data)
            logging.info("Pull summary email sent successfully.")
        except Exception as e:
            logging.error("Failed to send pull summary email: %s", str(e))
