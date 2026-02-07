from libraries import *

from modules.Helpers import *

from modules.Files_Field_Validator import load_file_mapping_config



def normalize_name(name: str) -> str:
    """
    Normalize filenames and aliases for matching:
    - lowercase
    - remove underscores, hyphens, spaces
    """
    norm = name.replace("-", "").replace("_", "").replace(" ", "").lower()
    logging.debug(f"Normalized '{name}' -> '{norm}'")
    return norm







# def get_candidate_document_links(candidate_folder_name: str):
#     """
#     Fetch only mapped candidate files from SFTP, convert to Base64, and map them to ERP keys.
#     Production-ready logs are printed for total files, mapped files, and unmapped files.

#     Returns:
#         dict: {ERP_KEY: base64_encoded_content}
#     """
#     links_mapping = {}
#     ssh = None
#     temp_dir = None
#     unmapped_files = []

#     try:
#         # 1️⃣ Connect to SFTP
#         logging.info(f"[START] Fetching documents for candidate folder: {candidate_folder_name}")
#         ssh, sftp = get_sftp_connection()
#         remote_folder_path = f"/bankonus/Outbound/Document/{candidate_folder_name}"

#         # 2️⃣ Check if remote folder exists
#         if not check_remote_dir(sftp, remote_folder_path):
#             logging.warning(f"[SKIP] Folder does not exist on SFTP: {remote_folder_path}")
#             return links_mapping

#         # 3️⃣ List files in folder
#         files = sftp.listdir(remote_folder_path)
#         total_files = len(files)
#         if total_files == 0:
#             logging.info(f"[SKIP] No files found in folder: {remote_folder_path}")
#             return links_mapping
#         logging.info(f"[INFO] Total files found for candidate '{candidate_folder_name}': {total_files}")

#         # 4️⃣ Load mapping rules
#         file_mapping_rules = load_file_mapping_config()
#         logging.info(f"[INFO] Loaded {len(file_mapping_rules)} ERP mapping rules")

#         # 5️⃣ Create temporary folder for downloading mapped files
#         temp_dir = tempfile.mkdtemp(prefix="candidate_docs_")
#         logging.info(f"[INFO] Temporary folder created: {temp_dir}")

#         mapped_count = 0

#         # 6️⃣ Process each file
#         for file_name in files:
#             filename_norm = normalize_name(file_name)
#             mapped_key = None

#             # Check mapping
#             for erp_key, aliases in file_mapping_rules.items():
#                 for alias in aliases:
#                     alias_norm = normalize_name(alias)
#                     if alias_norm in filename_norm:
#                         mapped_key = erp_key
#                         break
#                 if mapped_key:
#                     break

#             if mapped_key:
#                 # Download and encode only mapped files
#                 local_file_path = os.path.join(temp_dir, file_name)
#                 sftp.get(f"{remote_folder_path}/{file_name}", local_file_path)
#                 with open(local_file_path, "rb") as f:
#                     content = f.read()
#                     links_mapping[mapped_key] = base64.b64encode(content).decode("utf-8")
#                 mapped_count += 1
#             else:
#                 unmapped_files.append(file_name)

#         # 7️⃣ Production-ready summary
#         print("-" * 50)
#         print(f"Candidate Folder: {candidate_folder_name}")
#         print(f"Total files found: {total_files}")
#         print(f"Files mapped successfully: {mapped_count}")
#         print(f"Files skipped/unmapped: {len(unmapped_files)}")
#         if unmapped_files:
#             print("Unmapped files:", ", ".join(unmapped_files))
#         print("-" * 50)

#     except Exception as e:
#         logging.error(f"[ERROR] Failed processing documents for {candidate_folder_name}: {e}")

#     finally:
#         # Cleanup
#         if ssh:
#             ssh.close()
#             logging.info("[INFO] SFTP connection closed")
#         if temp_dir and os.path.exists(temp_dir):
#             shutil.rmtree(temp_dir)
#             logging.info(f"[INFO] Temporary folder removed: {temp_dir}")

#     return links_mapping
from concurrent.futures import ThreadPoolExecutor, as_completed

def get_candidate_document_links(candidate_folder_name: str):
    """
    Fetch mapped candidate files from SFTP, convert to Base64 in parallel, and map to ERP keys.
    Returns: {ERP_KEY: base64_encoded_content}
    """
    links_mapping = {}
    ssh = None
    temp_dir = None
    unmapped_files = []

    try:
        logging.info(f"[START] Fetching documents for candidate folder: {candidate_folder_name}")
        ssh, sftp = get_sftp_connection()
        remote_folder_path = f"/bankonus/Outbound/Document/{candidate_folder_name}"

        if not check_remote_dir(sftp, remote_folder_path):
            logging.warning(f"[SKIP] Folder does not exist on SFTP: {remote_folder_path}")
            return links_mapping

        files = sftp.listdir(remote_folder_path)
        total_files = len(files)
        if total_files == 0:
            logging.info(f"[SKIP] No files found in folder: {remote_folder_path}")
            return links_mapping
        logging.info(f"[INFO] Total files found: {total_files}")

        file_mapping_rules = load_file_mapping_config()
        logging.info(f"[INFO] Loaded {len(file_mapping_rules)} ERP mapping rules")

        temp_dir = tempfile.mkdtemp(prefix="candidate_docs_")
        logging.info(f"[INFO] Temporary folder created: {temp_dir}")

        def process_file(file_name):
            """Download, encode, and map a single file"""
            filename_norm = normalize_name(file_name)
            mapped_key = None

            for erp_key, aliases in file_mapping_rules.items():
                for alias in aliases:
                    if normalize_name(alias) in filename_norm:
                        mapped_key = erp_key
                        break
                if mapped_key:
                    break

            if mapped_key:
                local_file_path = os.path.join(temp_dir, file_name)
                sftp.get(f"{remote_folder_path}/{file_name}", local_file_path)
                with open(local_file_path, "rb") as f:
                    content = f.read()
                return mapped_key, base64.b64encode(content).decode("utf-8"), file_name
            else:
                return None, None, file_name

        # Run downloads/encodes in parallel
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [executor.submit(process_file, f) for f in files]
            for future in as_completed(futures):
                mapped_key, encoded_content, file_name = future.result()
                if mapped_key:
                    links_mapping[mapped_key] = encoded_content
                else:
                    unmapped_files.append(file_name)

        # Summary
        mapped_count = len(links_mapping)
        print("-" * 50)
        print(f"Candidate Folder: {candidate_folder_name}")
        print(f"Total files found: {total_files}")
        print(f"Files mapped successfully: {mapped_count}")
        print(f"Files skipped/unmapped: {len(unmapped_files)}")
        if unmapped_files:
            print("Unmapped files:", ", ".join(unmapped_files))
        print("-" * 50)

    except Exception as e:
        logging.error(f"[ERROR] Failed processing documents for {candidate_folder_name}: {e}")

    finally:
        if ssh:
            ssh.close()
            logging.info("[INFO] SFTP connection closed")
        if temp_dir and os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"[INFO] Temporary folder removed: {temp_dir}")

    return links_mapping
