from libraries import *
from modules.helpers import *

def load_file_mapping_config(config_path="mapping.json"):
    """Loads the JSON rulebook with a fallback for flat or nested structures."""
    try:
        if not os.path.exists(config_path):
            logging.warning(f"⚠️ Mapping file {config_path} not found.")
            return {}
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            
            # 1. Try to get nested rules first
            rules = config.get("file_mapping_rules")
            
            # 2. If it's None (meaning it's a flat JSON), use the whole config
            if rules is None:
                rules = config
            
            logging.info(f"✅ Successfully loaded {len(rules)} mapping rules from {config_path}")
            return rules
            
    except Exception as e:
        logging.error(f"❌ Failed to parse mapping.json: {str(e)}")
        return {}


def normalize_name(name: str) -> str:
    """
    Normalize filenames and aliases for matching:
    - lowercase
    - remove underscores, hyphens, spaces
    """
    norm = name.replace("-", "").replace("_", "").replace(" ", "").lower()
    logging.debug(f"Normalized '{name}' -> '{norm}'")
    return norm


def get_candidate_document_links(candidate_folder_name: str):
    """
    Fetch files from SFTP for a candidate,
    DOWNLOAD locally first, then convert to base64,
    and map them to ERP keys using mapping rules.
    """
    links_mapping = {}
    ssh = None

    # Local temp directory (auto-created)
    local_tmp_dir = os.path.join(os.getcwd(), "tmp_docs", candidate_folder_name)
    os.makedirs(local_tmp_dir, exist_ok=True)

    try:
        logging.info(f"Connecting to SFTP to fetch documents for {candidate_folder_name}")
        ssh, sftp = get_sftp_connection()
        remote_folder_path = f"/bankonus/Outbound/Document/{candidate_folder_name}"

        # Check if folder exists
        if not check_remote_dir(sftp, remote_folder_path):
            logging.warning(f"Folder does not exist on SFTP: {remote_folder_path}")
            return links_mapping

        logging.info(f"✅ Remote directory exists: {remote_folder_path}")

        # List files
        files = sftp.listdir(remote_folder_path)
        if not files:
            logging.info(f"No files found in folder: {remote_folder_path}")
            return links_mapping

        logging.info(f"Found {len(files)} files")

        # Load mapping rules
        file_mapping_rules = load_file_mapping_config()
        logging.info(f"Loaded {len(file_mapping_rules)} mapping rules from JSON")

        # Process each file
        for file in files:
            logging.info(f"Processing file: {file}")

            filename = file
            if filename.startswith(candidate_folder_name + "_"):
                filename = filename[len(candidate_folder_name) + 1:]

            filename_norm = normalize_name(filename)
            mapped = False

            for erp_key, aliases in file_mapping_rules.items():
                for alias in aliases:
                    if normalize_name(alias) in filename_norm:
                        if erp_key in links_mapping:
                            mapped = True
                            break

                        remote_file_path = f"{remote_folder_path}/{file}"
                        local_file_path = os.path.join(local_tmp_dir, file)

                        try:
                            # -------- STEP 1: DOWNLOAD FILE ----------
                            sftp.get(remote_file_path, local_file_path)
                            logging.info(f"⬇️ Downloaded file to {local_file_path}")

                            # -------- STEP 2: CONVERT TO BASE64 -------
                            with open(local_file_path, "rb") as lf:
                                file_bytes = lf.read()

                            links_mapping[erp_key] = base64.b64encode(file_bytes).decode("utf-8")
                            logging.info(f"✅ Converted '{file}' to base64 for ERP key '{erp_key}'")

                            mapped = True
                            break

                        except Exception as e:
                            logging.error(f"❌ Failed processing file {file}: {str(e)}")
                            mapped = True
                            break

                if mapped:
                    break

            if not mapped:
                logging.warning(f"❌ No mapping found for file: {file}")

    except Exception as e:
        logging.error(f"Error fetching or mapping documents for {candidate_folder_name}: {str(e)}")

    finally:
        if ssh:
            ssh.close()
            logging.info(f"SFTP connection closed for folder {candidate_folder_name}")

    return links_mapping
    







