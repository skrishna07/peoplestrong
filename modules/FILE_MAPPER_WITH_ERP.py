import json
import os
from modules.helpers import log_event

def load_mapping_config(config_path="mapping.json"):
    """Loads the JSON rulebook for file keywords."""
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Missing config: {config_path}")
        
        with open(config_path, 'r') as f:
            config = json.load(f)
            rules = config.get("file_mapping_rules", {})
            log_event(f"Successfully loaded {len(rules)} mapping rules from JSON.")
            return rules
    except Exception as e:
        log_event(f"Failed to load mapping.json: {str(e)}", is_error=True)
        return {}

def map_sftp_to_erp(sftp_links, mapping_rules):
    """
    Matches SFTP URLs to ERP Keys using keywords.
    Priority: First match in mapping_rules wins.
    """
    matched_files = {}

    for link in sftp_links:
        # Extract just the filename from the URL/Path
        filename = link.split('/')[-1].lower()
        
        # Skip specific 'download' duplicates mentioned in candidate docs
        if "download_and_upload" in filename:
            continue

        for erp_key, keywords in mapping_rules.items():
            if any(word.lower() in filename for word in keywords):
                # Map the full link to the specific ERP category
                matched_files[erp_key] = link
                log_event(f"Matched: {filename} -> {erp_key}")
                break # Stop searching rules for this specific file
                
    return matched_files







import pandas as pd

# Mapping from your CSV/PS keys to ERP keys
ERP_FIELD_MAP = {
    "First Name": "Person-firstname",
    "Last Name": "Person-lastname",
    "Gender": "Person-gender_id|disp",
    "Birth Date": "Person-birthdate",
    "Religion": "Person-religion_id|disp",
    "maritalstatus": "Person-maritalstatus_id|disp",
    "nationality": "Person-nationality_id|disp",
    "AltPhone": "AltPhone",
    "Alt Phone ISD": "AltPhoneDetails",
    "Alt Email": "Email",
    "Legal status": "EmployeeContract-legalstatus_id|disp",
    "Probation": "EmployeeContract-probationperiod|disp",
    "Notice Period": "EmployeeContract-noticeperiod|disp",
    "Date of joining": "EmployeeContract-doj",
    "Amount": "SalaryHead-Basic",
    "PayCodeName": "SalaryHead-Basic",  # optional if multiple salary heads
    "Edu Level": "EmpCustomization-edu_level",
    "Specialization": "EmpCustomization-specialization",
    "ID Number": "EmpCustomization-id_number",
    "ID Type": "EmpCustomization-id_type",
    "Valid Till": "EmpCustomization-valid_till"
}

def field_map_inspector(candidate_fields: dict, matched_docs: dict) -> dict:
    """
    Transforms PeopleStrong candidate fields into ERP-ready payload.
    
    Args:
        candidate_fields (dict): Raw candidate row dict from DataFrame.
        matched_docs (dict): Files mapped for the candidate.

    Returns:
        dict: ERP-ready payload with transformed field names, formatted dates, phone, numbers, and files.
    """
    erp_data = {}

    for src_field, erp_field in ERP_FIELD_MAP.items():
        val = candidate_fields.get(src_field)
        
        # Format dates to YYYY-MM-DD
        if src_field in ["Birth Date", "Date of joining", "Valid Till"] and val:
            try:
                val = pd.to_datetime(val, dayfirst=True).strftime("%Y-%m-%d")
            except Exception:
                pass  # keep original if parsing fails
        
        # Convert numeric fields
        if src_field in ["Amount"] and val:
            try:
                val = float(val)
            except Exception:
                val = 0.0
        
        if val is not None:
            erp_data[erp_field] = val

    # Format phone number: "971-521228656"
    alt_phone = erp_data.get("AltPhone")
    alt_details = erp_data.get("AltPhoneDetails", "")
    if alt_phone:
        erp_data["AltPhone"] = f"{alt_details}-{alt_phone}" if alt_details else alt_phone

    # Build ERP-ready payload
    erpid = str(candidate_fields.get("ERPID", "0"))
    payload = {
        "data": {
            erpid: {
                "data": erp_data,
                "files": matched_docs
            }
        }
    }

    return payload
