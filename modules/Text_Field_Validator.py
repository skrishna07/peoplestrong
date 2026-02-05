

from libraries import *


from modules.helpers import log_event


def load_text_mapping_config(config_path="text_data.json"):
    """Loads the JSON rulebook for text fields."""
    try:
        if not os.path.exists(config_path):
            raise FileNotFoundError(f"Missing config: {config_path}")
        
        with open(config_path, 'r') as f:
            # Load the JSON directly as the rules dictionary
            rules = json.load(f) 
            log_event(f"Successfully loaded {len(rules)} mapping rules from JSON.")
            return rules
    except Exception as e:
        log_event(f"Failed to load mapping.json: {str(e)}", is_error=True)
        return {}
    

def convert_to_months(value):
    """
    Converts a value in days or numeric to months.
    Minimum 1 month.
    Returns integer number of months.
    """
    try:
        val_str = str(value).lower()
        if 'day' in val_str:
            num = int(''.join(filter(str.isdigit, val_str)))
            months = -(-num // 30)  # ceiling division
            return max(1, months)
        else:
            num = int(float(value))
            if num <= 30:
                return 1
            return -(-num // 30)
    except:
        return 1
    



def field_inspector(payload_text):
    """
    Silent Fixer: Reprograms data formats on the fly.
    Returns ONLY the payload, ready for the ERP.
    """
    fixed_payload = {}
    
    # Mapping labels to the Integer IDs the ERP demanded
    legal_status_ids = {
    "ksatempvisa": 1,
    "billingcontract": 2,
    "payrollonly": 3,
    "servicevisa": 4,
    "visaapplicant": 5,
    "missionvisa": 6,
    "lcapplicant6month": 7,
    "lcapplicant1year": 8,
    "lcapplicant2year": 9
}
    

    employee_status_ids={
        "Single":1,
        "Married":2
    }


    for key, val in payload_text.items():
        # Clean the value
        if pd.isna(val) or str(val).strip().lower() in ['nan', '', 'n/a']:
            fixed_payload[key] = "" # Send empty string rather than crashing
            continue
            
        val = str(val).strip()

        # --- AUTO-FIX LOGIC ---

        # 1. Force Integer for Legal Status
        if key == "EmployeeContract-legalstatus_id":
            fixed_payload[key] = legal_status_ids.get(val, 1) # Default to 1 if label not found
        if key == "EmployeeContract-employeestatus_id|disp":
            fixed_payload["EmployeeContract-employeestatus_id|disp"] = employee_status_ids.get(val, 1)


        if key == "AltPhone":

            if "-" not in val:
                fixed_payload[key] = f"971-{val}"
            else:
                fixed_payload[key] = val

        # 2. Force YYYY-MM-DD for all Date fields
        elif any(x in key.lower() for x in ["date", "till", "doj", "start", "end", "birth"]):
            try:
                fixed_payload[key] = pd.to_datetime(val).strftime('%Y-%m-%d')
            except:
                fixed_payload[key] = val # Pass as-is if date logic fails

        # 3. Force 0.0000 for all Currency/Amount fields
        elif any(x in key.lower() for x in ["total", "amount", "basic"]):
            try:
                fixed_payload[key] = "{:.4f}".format(float(val))
            except:
                fixed_payload[key] = "0.0000"

        # 4. Strip .0 from ID Numbers and Pincodes (Pandas float fix)
        elif any(x in key.lower() for x in ["pincode", "number", "id_number"]):
            fixed_payload[key] = val.split('.')[0]

        # 5. All other 40 fields pass through clean
        else:
            fixed_payload[key] = val

    return fixed_payload
   
def normalize_name(name: str) -> str:
    """
    Normalize filenames and aliases for matching:
    - lowercase
    - remove underscores, hyphens, spaces
    """
    norm = name.replace("-", "").replace("_", "").replace(" ", "").lower()
    logging.debug(f"Normalized '{name}' -> '{norm}'")
    return norm
 

