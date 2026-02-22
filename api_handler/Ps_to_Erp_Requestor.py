
from libraries import *




def generate_curl(erpid, payload_json, headers):
    return f"""
curl -X PUT https://{ERP_HOST}{ERP_ENDPOINT} \\
  -H "auth: {headers['auth']}" \\
  -H "Content-Type: application/json" \\
  -d '{payload_json}'
""".strip()

def send_to_erp(erpid, payload_data, file_data=None):
    """
    Send candidate data to ERP using HTTP PUT.
    payload_data: dict of candidate fields
    file_data: dict of ERP key -> Base64 file
    """
    if not is_erp_id_valid(erpid):
        logging.warning(f"❌ ERP ID {erpid} is INVALID")
        return "FAILED", f"ERP ID {erpid} not valid in system"
    else:
        
        try:
            headers = {
                "auth": AUTH_TOKEN,
                "Content-Type": "application/json"
            }

            payload = {
                "data": {
                    get_erp_numeric_key(erpid): {
                        "data": payload_data,
                        "files": file_data if file_data else {}
                    }
                }
            }

            payload_json = json.dumps(payload)

            # Send request
            conn = http.client.HTTPSConnection(ERP_HOST)
            conn.request("PUT", ERP_ENDPOINT, body=payload_json, headers=headers)
            res = conn.getresponse()

            # Save curl command for cross-check
            curl_cmd = generate_curl(erpid, payload_json, headers)
            output_dir = "/home/tahoeerp/Documents/peoplestrong/curl_debug"
            os.makedirs(output_dir, exist_ok=True)
            curl_file_name=os.path.join(output_dir,"cross_check_payload.curl")
            with open(curl_file_name, "w", encoding="utf-8") as f:
                f.write(curl_cmd)

            res_data = res.read().decode("utf-8")
            print(f"[ERP RESPONSE for {erpid}]")
            print(res_data)

            res_json = json.loads(res_data)

            # Handle ERP response
            if res.status in [200, 201]:
                errors = res_json.get("upload_errors", {})
                if not errors:
                    logging.info(f"✅ Sync Success: {erpid}")
                    return "SUCCESS", "Synced Successfully"
                else:
                    error_str = "; ".join([f"{k}: {', '.join(v)}" for k, v in errors.items()])
                    logging.warning(f"❌ Validation Failed for {erpid}: {error_str}")
                    return "FAILED", error_str or f"Server Rejected {res.status}"

            else:
                logging.error(f"❌ Server Rejected {res.status}: {res_data}")
                return "FAILED", f"Server Rejected {res.status}"

        except Exception as e:
            logging.error(f"❌ Connection Error: {str(e)}")
            return "FAILED", str(e)





def is_erp_id_valid(employee_id: str) -> bool:
    """
    Returns True if ERP ID exists and is valid in the bankonusimport API,
    False otherwise.
    """
    if not employee_id:
        logging.warning("[ERP CHECK] No employee_id provided")
        return False

    url = f"https://erp.innovationuae.com/api/web/bankonusimport?employee_ids={employee_id}&="
    headers = {
        "auth": AUTH_TOKEN,
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()

        if response.status_code == 200 and data.get("status") == "OK":
            # Iterate over numeric keys
            for top_key, emp_data in data.get("data", {}).items():
                emp_info = emp_data.get("data", {})
                contract_code = emp_info.get("EmployeeContract-clientcode", "")
                if contract_code.lower() == employee_id.lower():
                    logging.info(f"[ERP CHECK] ERP ID {employee_id} is VALID")
                    return True

            logging.info(f"[ERP CHECK] ERP ID {employee_id} NOT FOUND in ERP data")
            return False

        if response.status_code == 400 or data.get("status") == "ERROR":
            logging.info(f"[ERP CHECK] ERP ID {employee_id} NOT VALID (ERP returned error)")
            return False

        response.raise_for_status()

    except requests.RequestException as e:
        logging.error(f"[ERP CHECK ERROR] {employee_id}: {e}")
        return False
    




def get_erp_numeric_key(employee_id: str) -> str | None:
    """
    Call bankonusimport API and return the numeric ERP key (like 112451) if present.
    Returns None if not found or on error.
    """
    if not employee_id:
        logging.warning("[ERP] No employee_id provided")
        return None

    url = f"https://erp.innovationuae.com/api/web/bankonusimport?employee_ids={employee_id}&="
    headers = {
        "auth": AUTH_TOKEN,
        "Accept": "application/json"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        data = response.json()

        if data.get("status") == "OK" and "data" in data:
            # Extract the first numeric key
            numeric_keys = [key for key in data["data"].keys() if key.isdigit()]
            if numeric_keys:
                return numeric_keys[0]

        logging.info(f"[ERP] Numeric key not found for employee_id {employee_id}")
        return None

    except requests.RequestException as e:
        logging.error(f"[ERP ERROR] Failed to fetch ERP key for {employee_id}: {e}")
        return None




def confirm_erp_update(employee_id: str, payload_data: dict, max_attempts=3, delay_sec=5) -> bool:
    """
    Confirm that ERP has the updated values for the given employee_id.
    Compares payload_data against current ERP data.
    
    Returns True if values match, False otherwise.
    """
    numeric_key = get_erp_numeric_key(employee_id)
    if not numeric_key:
        logging.warning(f"[ERP CONFIRM] Numeric key not found for {employee_id}")
        return False

    url = f"https://erp.innovationuae.com/api/web/bankonusimport?employee_ids={employee_id}&="
    headers = {"auth": AUTH_TOKEN, "Accept": "application/json"}

    for attempt in range(1, max_attempts + 1):
        try:
            response = requests.get(url, headers=headers, timeout=30)
            response.raise_for_status()
            data = response.json()

            if data.get("status") != "OK":
                logging.warning(f"[ERP CONFIRM] Attempt {attempt}: ERP status not OK")
                time.sleep(delay_sec)
                continue

            erp_data = data["data"].get(numeric_key, {}).get("data", {})
            if not erp_data:
                logging.warning(f"[ERP CONFIRM] Attempt {attempt}: No ERP data found")
                time.sleep(delay_sec)
                continue

            # Compare fields
            mismatches = []
            for k, v in payload_data.items():
                erp_val = erp_data.get(k)
                # Compare as string for safety
                if str(erp_val).strip() != str(v).strip():
                    mismatches.append((k, v, erp_val))

            if not mismatches:
                logging.info(f"[ERP CONFIRM] ✅ All values match for {employee_id}")
                return True
            else:
                logging.warning(f"[ERP CONFIRM] Attempt {attempt}: Mismatches found: {mismatches}")
                time.sleep(delay_sec)

        except requests.RequestException as e:
            logging.error(f"[ERP CONFIRM] Attempt {attempt}: Error fetching ERP data: {e}")
            time.sleep(delay_sec)

    logging.error(f"[ERP CONFIRM] ❌ Failed to confirm ERP update for {employee_id}")
    return False