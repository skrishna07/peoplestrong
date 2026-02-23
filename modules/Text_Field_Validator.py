

from libraries import *


from modules.Helpers import log_event


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
    

def to_days(val):
    try:
        s = str(val).lower()
        num = int("".join(filter(str.isdigit, s)))
        if "month" in s:
            return num * 30
        return num
    except:
        return None


def nearest_value(days, allowed_map):
    """
    allowed_map = { days: 'ERP Display Value' }
    """
    if days is None:
        return ""

    return allowed_map[min(allowed_map.keys(), key=lambda x: abs(x - days))]


def field_inspector(payload):
    legal_status_ids = {
        "visa applicant - current visa (employment visa)": 5,
        "service visa": 4,
        "payroll only": 3,
    }

    employee_status_ids = {
    "Prospective Hire": "Onboarding",  # ERP ID for Onboarding
    "Active": "Working"            # ERP ID for Working
}

    probation_allowed = {
        30: "1 Month",
        60: "2 Month",
        90: "3 Month",
        120: "4 Month",
        150: "5 Month",
        360: "12 Month"
    }

    notice_allowed = {
        0: "No Notice",
        7: "7 Days",
        10: "10 Days",
        15: "15 Days",
        60: "2 Months",
        90: "3 Months"
    }
    WORK_TYPE_IDS = {
    "full-time": 1,
    "part-time": 2,
    "contract": 3
}

    INSURANCE_IDS = {
        "eligible": 1,
        "not eligible": 2
    }

    AIRFARE_IDS = {
        "eligible": 1,
        "not eligible": 2
    }
    gender_ids = {
    "male": 1,
    "female": 2,
    "other": 3
}
    

    DEGREE_MAP = {
    "Ph.D": "Ph.D",
    "Doctorate": "Ph.D",
    "Master's Degree": "Master",
    "Master": "Master",
    "Post Graduation Diploma": "Post Graduation Diploma",
    "Associate's Degree/College Diploma": "Associate Diploma",
    "Bachelor's Degree": "Bachelor",
    "Bachelor": "Bachelor",
    "Diploma": "Diploma",
    "High School": "Diploma"  # optional fallback
}




    fixed = {}

    for k, v in payload.items():
        if v is None or str(v).strip().lower() in ("", "nan", "n/a"):
            fixed[k] = ""
            continue

        val = str(v).strip()

        # ---------- LEGAL STATUS ----------
        if k == "EmployeeContract-legalstatus_id":
            fixed[k] = legal_status_ids.get(val.lower(), 1)

        elif k == "Person-gender_id|disp":
            fixed[k] = gender_ids.get(val.lower(), "")


        # ---------- EMPLOYEE STATUS ----------
        elif k == "EmployeeContract-employeestatus_id|disp":
            #val is Prospective Hire
            fixed[k] = employee_status_ids.get(val.strip(), "Onboarding")

        # ---------- PROBATION ----------
        elif k == "EmployeeContract-probationperiod":
            days = to_days(val)
            fixed[k] = nearest_value(days, probation_allowed)

        # ---------- NOTICE PERIOD ----------
        elif k == "EmployeeContract-noticeperiod":
            days = to_days(val)
            fixed[k] = nearest_value(days, notice_allowed)

        # ---------- DATE FIELDS ----------
        elif any(x in k.lower() for x in ("date", "start", "end", "birth")):
            try:
                fixed[k] = pd.to_datetime(val).strftime("%Y-%m-%d")
            except:
                fixed[k] = ""

        # ---------- SALARY ----------
        elif any(x in k.lower() for x in ("salary", "basic", "hra", "total")):
            try:
                fixed[k] = f"{float(val):.4f}"
            except:
                fixed[k] = "0.0000"
        elif k == "EmployeeContract-worktype|disp":
            fixed[k] = WORK_TYPE_IDS.get(val.lower(), 1)

        elif k == "EmployeeContract-insuranceeligibiity_id|disp":
            fixed[k] = INSURANCE_IDS.get(val.lower(), 1)

        elif k == "EmployeeContract-airfareeligibility|disp":
            fixed[k] = AIRFARE_IDS.get(val.lower(), 1)
        elif k == "Qualification-degreetype|disp":
            fixed[k] =  DEGREE_MAP.get(val, "Diploma") 


        else:
            fixed[k] = val

    logging.info(f"[FIELD_INSPECTOR] Payload sanitized safely (fields={len(fixed)})")
    return fixed


def normalize_name(name: str) -> str:
    """
    Normalize filenames and aliases for matching:
    - lowercase
    - remove underscores, hyphens, spaces
    """
    norm = name.replace("-", "").replace("_", "").replace(" ", "").lower()
    logging.debug(f"Normalized '{name}' -> '{norm}'")
    return norm
 

