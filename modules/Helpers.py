from libraries import *



STATUS_PENDING = "PENDING"
STATUS_FAILED = "FAILED"
STATUS_SUCCESS = "SUCCESS"
# =====================================================
# Helper functions for SFTP
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






def get_sftp_connection():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(os.environ["SFTP_HOST"], port=2222, username=os.environ["SFTP_USER"], password=os.environ["SFTP_PASS"])
    return ssh, ssh.open_sftp()



def safe_archive_file(sftp, source_path, archive_dir, move_file=True):
    """
    Archive a file on SFTP.

    move_file=True  → Permanent archive (MOVE)
    move_file=False → Temporary archive (COPY)
    """

    filename = os.path.basename(source_path)
    target_path = f"{archive_dir}/{filename}"

    archive_mode = "PERMANENT (MOVE)" if move_file else "TEMPORARY (COPY)"
    logging.info(f"[ARCHIVE MODE] {archive_mode} | File: {filename}")

    # Ensure archive directory exists
    try:
        sftp.stat(archive_dir)
    except IOError:
        logging.info(f"[ARCHIVE] Creating archive directory: {archive_dir}")
        sftp.mkdir(archive_dir)

    # Remove existing file in archive if present
    try:
        sftp.remove(target_path)
        logging.info(f"[ARCHIVE] Removed old archive file: {filename}")
    except IOError:
        pass

    try:
        if move_file:
            sftp.rename(source_path, target_path)
            logging.info(f"[ARCHIVE] MOVE completed → {filename}")
        else:
            with sftp.open(source_path, "rb") as src, sftp.open(target_path, "wb") as dst:
                dst.write(src.read())
            logging.info(f"[ARCHIVE] COPY completed → {filename}")
    except Exception as e:
        logging.error(f"[ARCHIVE ERROR] {filename}: {e}")


def is_not_duplicate(sftp, target_dir, emp_id, doc_code):
    """Client Spec: Combination of Candidate ID and Doc Code should not be duplicate"""
    try:
        existing_files = sftp.listdir(target_dir)
        # Unique prefix for checking: ID_DocCode
        prefix = f"{emp_id}_{doc_code.replace(' ', '')}"
        return not any(f.startswith(prefix) for f in existing_files)
    except:
        return True





# =====================================================
# 1. VALIDATION GATES WITH LOGGING
# =====================================================

def is_size_valid(file_content, filename):
    MAX_SIZE_BYTES = 5 * 1024 * 1024
    size_mb = len(file_content) / (1024 * 1024)
    if len(file_content) <= MAX_SIZE_BYTES:
        return True
    logging.warning(f"  [VALIDATION FAIL] {filename} too large: {size_mb:.2f}MB")
    return False

def is_format_valid(filename):
    allowed = {'.pdf', '.xls', '.jpeg', '.jpg', '.doc', '.docx', '.xlsx', '.zip', '.png'}
    _, ext = os.path.splitext(filename.lower())
    if ext in allowed:
        return True
    logging.warning(f"  [VALIDATION FAIL] {filename} invalid extension: {ext}")
    return False







def log_event(message, is_error=False):
    """
    Logs messages to specific files based on the status.
    Path: ./logs/
    """
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    log_dir = "logs"
    
    # Ensure directory exists
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    file_name = "errors.txt" if is_error else "Automation.txt"
    file_path = os.path.join(log_dir, file_name)

    log_entry = f"[{timestamp}] {'ERROR: ' if is_error else 'INFO: '} {message}\n"
    
    with open(file_path, "a") as f:
        f.write(log_entry)

    # Also print to console for real-time monitoring
    print(log_entry.strip())














    ######################Mapper









#======================================
def safe(v):
    return v if pd.notna(v) and str(v).strip() else ""

def fmt_date(v):
    try:
        return pd.to_datetime(v).strftime("%Y-%m-%d")
    except:
        return ""



def scalar(val):
    """
    Always return a clean scalar string for ERP.
    Handles Series, NaN, None safely.
    """
    if isinstance(val, pd.Series):
        if val.empty:
            return ""
        val = val.iloc[0]
    if pd.isna(val):
        return ""
    return str(val).strip()





def print_peoplestrong_snapshot(row):
    print("\n" + "=" * 100)
    print("🟢 PEOPLESTRONG DATA SNAPSHOT (BEFORE ERP MAPPING)")
    print("=" * 100)

    # ---------------- CORE / PERSONAL DETAILS ----------------
    print("\n📌 CORE / PERSONAL DETAILS")
    personal_cols = [
        "Candidate ID","Title","First Name","Middle Name","Last Name",
        "Gender","Mothers Name","Birth Date","maritalstatus",
        "Religion","nationality","Alt Phone ISD","Alt Phone","Alt Email",
        "Contract Clause","Legal status","Probation","Notice Period",
        "working hours","work type","insurance eligibility",
        "airfare eligibility","client designation",
        "client authorization details","Date of joining",
        "Final Employment Status"
    ]
    for c in personal_cols:
        print(f"{c:35} : {row.get(c, '')}")

    # ---------------- ADDRESS DETAILS ----------------
    print("\n🏠 ADDRESS DETAILS")
    address_cols = [
        "Address Type","AddressLine1","AddressLine2","AddressLine3",
        "PIN","City","District","State","Country","Mobile No",
        "LocalAddress","HomeAddress"
    ]
    for c in address_cols:
        print(f"{c:35} : {row.get(c, '')}")

    # ---------------- EDUCATION DETAILS ----------------
    print("\n🎓 EDUCATION DETAILS")
    edu_cols = [
        "Edu Level","Specialization","Institute Name",
        "Start Date","End Date","Is Highest Qualification"
    ]
    for c in edu_cols:
        print(f"{c:35} : {row.get(c, '')}")

    # ---------------- EMERGENCY CONTACT ----------------
    print("\n🚨 EMERGENCY CONTACT")
    emergency_cols = [
        "Emergency Contact Number",
        "Emergency Contact Relation",
        "Emergency Contact Name"
    ]
    for c in emergency_cols:
        print(f"{c:35} : {row.get(c, '')}")

    # ---------------- ID DETAILS ----------------
    print("\n🪪 ID DETAILS")
    id_cols = [
        "Passport-number","Passport-issuedate","Passport-issueplace","Passport-expiry",
        "SponsorPassport-number","SponsorPassport-issuedate","SponsorPassport-issueplace","SponsorPassport-expiry",
        "EmiratesID-number","EmiratesID-issuingdate","EmiratesID-expirydate",
        "SponsorEmiratesID-number","SponsorEmiratesID-issuingdate","SponsorEmiratesID-expirydate",
        "SponsorVisa-number","SponsorVisa-placeofissue","SponsorVisa-startdate","SponsorVisa-enddate",
        "NOC-number","NOC-issuedate","NOC-expirydate",
        "MedicalInsurance-number","MedicalInsurance-issuedate","MedicalInsurance-expirydate"
    ]
    for c in id_cols:
        print(f"{c:35} : {row.get(c, '')}")

    # ---------------- SALARY DETAILS ----------------
    print("\n💰 SALARY DETAILS")
    salary_cols = [
        "Salary_Basic","Salary_HRA","Salary_Food",
        "Salary_Transport","Salary_Telephone",
        "Salary_Other","Salary_Variable",
        "Salary_AnnualLeave","Salary_Airfare",
        "Salary_EffectiveDate"
    ]
    for c in salary_cols:
        print(f"{c:35} : {row.get(c, '')}")

    print("=" * 100 + "\n")
