from libraries import *
import datetime

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
            # Ensure the link format includes folder prefix in filename
            if not file.startswith(candidate_folder_name):
                file = f"{candidate_folder_name}_{file}"
            link = f"{base_link}{remote_folder_path}/{file}"
            links.append(link)

    except Exception as e:
        logging.error(f"Error fetching document links for {candidate_folder_name}: {str(e)}")
    finally:
        if ssh:
            ssh.close()
    return links






def get_sftp_connection():
    ssh = paramiko.SSHClient()
    ssh.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    ssh.connect(os.environ["SFTP_HOST"], port=2222, username=os.environ["SFTP_USER"], password=os.environ["SFTP_PASS"])
    return ssh, ssh.open_sftp()

def safe_archive_file(sftp, source_path, archive_dir):
    filename = os.path.basename(source_path)
    target_path = f"{archive_dir}/{filename}"
    try:
        sftp.stat(archive_dir)
    except IOError:
        sftp.mkdir(archive_dir)
    try:
        sftp.remove(target_path)
    except IOError:
        pass
    sftp.rename(source_path, target_path)




    

def get_verified_doc_code(erp_label):
    """Client Spec: Labour Card, Stamped Visa and EID Copy"""
    mapping = {
        "labour_card": "Labour Card",
        "visa": "Stamped Visa",
        "eid": "EID Copy"
    }
    return mapping.get(erp_label.lower(), "Labour Card")

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
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
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


def format_alt_phone(phone_input):
    """
    Strictly formats the AltPhone string for the Innovation ERP.
    Input: "+971521228656"
    Output: "971-521228656"
    """
    # 1. Strip all non-numeric characters
    digits = re.sub(r'\D', '', str(phone_input))
    
    # 2. Apply formatting logic
    if digits.startswith('971'):
        return f"971-{digits[3:]}"
    elif digits.startswith('0'):
        # Converts local 052... to 971-52...
        return f"971-{digits[1:]}"
    else:
        # Fallback: Hyphenate after first 3 digits
        return f"{digits[:3]}-{digits[3:]}"