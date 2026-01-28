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
from modules.send_email_summary import send_push_summary_email,send_pull_summary_email


# Load .env file
load_dotenv()

# # Environment variables
# JOIN_KEY = os.getenv('JOIN_KEY')
# DOC_DIR = os.getenv('DOC_DIR')
# INPUT_DIR = os.getenv('INPUT_DIR')
# ARCHIVE_DIR = os.getenv('ARCHIVE_DIR')
# IMPORT_DIR = os.getenv('IMPORT_DIR')
# ERP_URL = os.getenv("ERP_API_URL")
# AUTH_TOKEN = os.getenv("ERP_AUTH_TOKEN")




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

def check_remote_dir(sftp, remote_path):
    """Check if remote directory exists"""
    try:
        sftp.chdir(remote_path)
        print(f"✅ Remote directory exists: {remote_path}")
        return True
    except IOError:
        print(f"❌ Remote directory NOT found: {remote_path}")
        return False
    



def create_remote_folder(sftp, remote_path):
    """Create remote folder if it doesn't exist"""
    if not check_remote_dir(sftp, remote_path):
        print(f"📁 Creating remote folder: {remote_path}")
        sftp.mkdir(remote_path)
    else:
        print(f"✅ Remote folder already exists: {remote_path}")

def get_candidate_document_links(candidate_folder_name: str):
    """
    Given a candidate folder name inside the Document directory, 
    returns a list of SFTP file links for all files in that folder.
    """
    links = []
    ssh = None
    try:
        ssh, sftp = get_sftp_connection()
        remote_folder_path = f"/bankonus/Outbound/Document/{candidate_folder_name}"

        if not check_remote_dir(sftp, remote_folder_path):
            logging.warning(f"Folder does not exist on SFTP: {remote_folder_path}")
            return links

        files = sftp.listdir(remote_folder_path)
        if not files:
            logging.info(f"No files found in folder: {remote_folder_path}")
            return links

        base_link = "https://datavault.peoplestrong.com/file/d"
        for file in files:
            link = f"{base_link}{remote_folder_path}/{file}"
            links.append(link)

    except Exception as e:
        logging.error(f"Error fetching document links for {candidate_folder_name}: {str(e)}")
    finally:
        if ssh:
            ssh.close()
    return links


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
                    payload = {"employee_ids": [erpid], "data": row.where(pd.notnull(row), None).to_dict()}
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
                        res = requests.post(ERP_URL, headers=headers, json=payload, params=params, timeout=60)
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

# =====================================================
# CALL FUNCTIONS DIRECTLY
# =====================================================
if __name__ == "__main__":
    PS_to_ERP_Push()
    # ERP_to_PS_Pull()
