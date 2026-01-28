import os
import io
import logging
import traceback
import requests
import paramiko
import pandas as pd
from datetime import datetime
import json
from modules.helpers import *
from dotenv import load_dotenv 
from modules.send_email_summary import send_push_summary_email, send_pull_summary_email
import curlify
from modules.file_mapper_with_erp import map_sftp_to_erp

from libraries import *
# Load .env file
load_dotenv()

# Environment variables with defaults
SFTP_HOST = os.getenv("SFTP_HOST", "datavault.peoplestrong.com")
SFTP_USER = os.getenv("SFTP_USER", "bankonus")
SFTP_PASS = os.getenv("SFTP_PASS", "B@n1%u$#90")
SFTP_PORT = int(os.getenv("SFTP_PORT", 2222))

ERP_URL = os.getenv("ERP_API_URL", "https://erp.innovationuae.com/api/web/bankonusimport/")
AUTH_TOKEN = os.getenv("ERP_AUTH_TOKEN", "eyJpdiI6Ik1rYnh1Ty9nZENjR2dTdWpkMjNXcmc9PSIsInZhbHVlIjoidGF4a0lhb252QjFVSUhVeHhBcGMzdU5uZTFzU3liVkxXWGlsV2svR3VoZzNIN1Q2Uy9HMlRzdHlOR3NuVS9rSENlcFJ3cGZIK2tmYS9vU2Q0bXV1c2c9PSIsIm1hYyI6ImUwZTVmZTg4ZGQyYjAwNjZiNGM3MzBhOWZiMjBjZDNmNzYzMDhhOWFlNjUxODRlZWM2MDEwMDliNDc2NWE0Y2YiLCJ0YWciOiIifQ")

ERP_TEST_IDS = os.getenv("ERP_TEST_IDS", "115976,115977,115978,115979")
JOIN_KEY = os.getenv("JOIN_KEY", "Candidate ID")
DOC_DIR = os.getenv("DOC_DIR", "/bankonus/Inbound/Documents")
INPUT_DIR = os.getenv("INPUT_DIR", "/bankonus/Inbound/Input")
ARCHIVE_DIR = os.getenv("ARCHIVE_DIR", "/bankonus/Outbound/Archive")
IMPORT_DIR = os.getenv("IMPORT_DIR", "/bankonus/Outbound/Output")

# Logger setup
logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')


# =====================================================
# 1. PS_to_ERP_Push
# =====================================================
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
                        curl_command = curlify.to_curl(res.request)
                        print("##############################",payload)
                        
                        if res.status_code in [200, 201]:
                            logging.info("SUCCESS: ERP accepted %s", erpid)
                            record_status["status"] = "SUCCESS"
                            record_status["comments"] = "All the Fields Extracted Successfully"
                            

                            curl_file_path = r"C:\Users\BRADSOL\Downloads\People_Strong\erp_curl_requests.txt"
                            with open(curl_file_path, "a", encoding="utf-8") as f:
                                f.write(curl_command + "\n\n")

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
            try:
                send_push_summary_email(push_data)
            except Exception as e:
                logging.error("Failed to send summary email: %s", str(e))

    except Exception as e:
        logging.critical("CRITICAL FAILURE: %s", str(e))
        logging.error(traceback.format_exc())

    finally:
        if ssh:
            ssh.close()
            logging.info("SFTP Connection Closed.")
            logging.info("="*60)

# =====================================================
# 2. ERP_to_PS_Pull
# =====================================================

# =====================================================
# CALL FUNCTIONS DIRECTLY
# =====================================================
if __name__ == "__main__":
    PS_to_ERP_Push()
    # ERP_to_PS_Pull()
