

import paramiko
import os
import warnings
from cryptography.utils import CryptographyDeprecationWarning
from libraries import *


LOCAL_FOLDER = os.path.join(os.getcwd(), "Data_files")


def check_remote_dir(sftp, remote_path):
    """Check if remote directory exists without creating it"""
    try:
        sftp.chdir(remote_path)
        print(f"✅ Remote directory exists: {remote_path}")
        return True
    except IOError:
        print(f"❌ Remote directory NOT found: {remote_path}")
        return False

def upload_files_to_ps():
    ssh = None
    try:
        ssh = paramiko.SSHClient()
        ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh.connect(
            SFTP_HOST,
            port=SFTP_PORT,
            username=SFTP_USER,
            password=SFTP_PASS
        )
        

        sftp = ssh.open_sftp()
        print("✅ Connected to PeopleStrong SFTP")

        # --- STEP 1: CHECK REQUIRED REMOTE DIRECTORIES ---
        required_dirs = [
            IMPORT_DIR,
            ARCHIVE_DIR,
            LOG_DIR
            
        ]

        for directory in required_dirs:
            if not check_remote_dir(sftp, directory):
                raise Exception(f"Required remote directory missing: {directory}")

        # Ensure we're in target upload directory
        sftp.chdir(IMPORT_DIR)

        # --- STEP 2: UPLOAD FILES ---
        files_to_upload = [
            'CandidateData',
            'CandidateContact',
            'CandidateEducation',
            'CandidateEmergencyContact',
            'CandidateIDDetails',
            'CandidateSalaryData',
            'Mapping'
        ]

        for file_prefix in files_to_upload:
            try:
                local_files = [
                    f for f in os.listdir(LOCAL_FOLDER)
                    if f.startswith(file_prefix)
                ]

                if not local_files:
                    print(f"⚠️ No local file found for prefix: {file_prefix}")
                    continue

                filename = local_files[0]
                local_path = os.path.join(LOCAL_FOLDER, filename)
                remote_path = f"{LOG_DIR}/{filename}"

                print(f"🚀 Uploading: {filename}")
                sftp.put(local_path, remote_path)
                print(f"✅ Uploaded successfully: {filename}")

            except Exception as file_err:
                print(f"❌ Error uploading {file_prefix}: {file_err}")

        print("🎊 File upload process completed.")

    except Exception as e:
        print(f"❌ Fatal Error: {e}")

    finally:
        if ssh:
            ssh.close()
            print("🔒 SFTP connection closed")

if __name__ == "__main__":
    upload_files_to_ps()
