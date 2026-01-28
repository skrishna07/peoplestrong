from libraries import *
from modules.helpers import *
# from modules.SEND_EMAIL_SUMMARY import send_push_summary_email
from modules.FILE_MAPPER_WITH_ERP import load_mapping_config, map_sftp_to_erp, field_map_inspector


def PS_to_ERP_Push():
    logging.info("="*60)
    logging.info(">>> DIGITAL RELAY: PEOPLESTRONG TO ERP SYNC STARTING <<<")
    logging.info("="*60)

    ssh = None
    push_data = []

    try:
        # STEP 1: SFTP CONNECTION
        logging.info("[STEP 1] Connecting to SFTP...")
        ssh, sftp = get_sftp_connection()
        all_files = sftp.listdir(IMPORT_DIR)
        data_frames = {}

        prefixes = ['CandidateData', 'Mapping', 'CandidateContact', 'CandidateSalaryData',
                    'CandidateEducation', 'CandidateIDDetails', 'CandidateEmergencyContact']

        # STEP 2: GATHER DATA
        logging.info("[STEP 2] Gathering CSV files...")
        for prefix in prefixes:
            matches = [f for f in all_files if f.startswith(prefix) and f.endswith('.csv')]
            if matches:
                latest_file = sorted(matches, reverse=True)[0]
                logging.info("  --> Found: %s", latest_file)
                with sftp.open(f"{IMPORT_DIR}/{latest_file}", "rb") as f:
                    df = pd.read_csv(io.BytesIO(f.read()), sep='|', dtype=str)
                    df.columns = df.columns.str.strip()
                    if prefix == 'Mapping':
                        logging.info("      [MAPPING] Activating Translator...")
                        df = df.rename(columns={'PeopleStrongID': JOIN_KEY})
                    data_frames[prefix] = df

        # STEP 3: DATA ASSEMBLY
        if 'CandidateData' in data_frames:
            logging.info("[STEP 3] Assembling master dataframe...")
            master_df = data_frames['CandidateData']
            for key in [k for k in data_frames.keys() if k != 'CandidateData']:
                if JOIN_KEY in data_frames[key].columns:
                    master_df = pd.merge(master_df, data_frames[key], on=JOIN_KEY, how='left')
                    logging.info("  + Integrated %s", key)

            if 'ERPID' in master_df.columns:
                master_df['ERPID'] = master_df['ERPID'].astype(str).str.split('.').str[0]
                final_df = master_df[master_df['ERPID'].notnull() & (master_df['ERPID'] != 'nan')].drop_duplicates(subset=['ERPID'])

                logging.info("[SUMMARY] Total Candidates: %d", len(master_df))
                logging.info("[SUMMARY] Valid Mapped: %d", len(final_df))

                # STEP 4: API DELIVERY
                logging.info("[STEP 4] Delivering to ERP...")
                for _, row in final_df.iterrows():
                    erpid = row.get('ERPID')
                    # Fetch candidate document links and add to payload
                    candidate_folder ="PH20251009105742907"
                    document_links = get_candidate_document_links(candidate_folder)
                    payload_data = row.where(pd.notnull(row), None).to_dict()
                    payload_data['documents'] = document_links
                    payload = {"employee_ids": [erpid], "data": payload_data}
                    params = {"employee_ids": erpid}

                    # Prepare record for email
                    record_status = {
                        "ERPID": erpid,
                        "data_extracted": json.dumps(payload, indent=2),  # full JSON
                        "status": "",
                        "comments": ""
                    }

                    try:
                        headers = {'auth': AUTH_TOKEN, 'Content-Type': 'application/json'}
                        res = requests.put(ERP_URL, headers=headers, json=payload, params=params, timeout=60) #put request
                        print("##############################",payload)
                        
                        if res.status_code in [200, 201]:
                            logging.info("SUCCESS: ERP accepted %s", erpid)
                            record_status["status"] = "SUCCESS"
                            record_status["comments"] = "All the Fields Extracted Successfully"
                            

                            

                        else:
                            logging.warning("REJECTED: %s | Status %d", erpid, res.status_code)
                            record_status["status"] = "FAILED"
                            record_status["comments"] = f"Status {res.status_code}"
                    except Exception as e:
                        logging.error("API ERROR for %s: %s", erpid, str(e))
                        record_status["status"] = "ERROR"
                        record_status["comments"] = str(e)

                    push_data.append(record_status)

            # STEP 5: CLEANUP & ARCHIVE
            logging.info("[STEP 5] Archiving files...")
            for f_name in all_files:
                try:
                    safe_archive_file(sftp, f"{IMPORT_DIR}/{f_name}", ARCHIVE_DIR)
                    logging.info("Archived: %s", f_name)
                except Exception as e:
                    logging.error("ARCHIVE ERROR: %s", str(e))

            # Send summary email
            # try:
            #     send_push_summary_email(push_data)
            # except Exception as e:
            #     logging.error("Failed to send summary email: %s", str(e))

    except Exception as e:
        logging.critical("CRITICAL FAILURE: %s", str(e))
        logging.error(traceback.format_exc())

    finally:
        if ssh:
            ssh.close()
            logging.info("SFTP Connection Closed.")
            logging.info("="*60)



