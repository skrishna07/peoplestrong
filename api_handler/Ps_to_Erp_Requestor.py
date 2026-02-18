
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
    try:
        headers = {
            "auth": AUTH_TOKEN,
            "Content-Type": "application/json"
        }

        payload = {
            "data": {
                erpid: {
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
        with open(r"C:\Users\BRADSOL\Downloads\PEOPLE_STRONG_WITH_PYTHON\cross_check_payload.curl", "w", encoding="utf-8") as f:
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
    Returns True if ERP ID exists and is valid, False otherwise.
    
    Uses the variables defined:
      ERP_API_URL / ERP_AUTH_TOKEN
    """
    if not employee_id:
        logging.warning("[ERP CHECK] No employee_id provided")
        return False

    url = f"https://erp.innovationuae.com//{ERP_ENDPOINT}?employee_ids={employee_id}&="
    headers = {
        "auth": AUTH_TOKEN,
        "Accept": "application/json",
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        data = response.json()

        # ID found if status=OK and employee_id in data
        if response.status_code == 200 and data.get("status") == "OK":
            if str(employee_id) in data.get("data", {}):
                logging.info(f"[ERP CHECK] ERP ID {employee_id} is VALID")
                return True
            else:
                logging.info(f"[ERP CHECK] ERP ID {employee_id} NOT FOUND in ERP data")
                return False

        # 400 or status=ERROR → invalid ID
        if response.status_code == 400 or data.get("status") == "ERROR":
            logging.info(f"[ERP CHECK] ERP ID {employee_id} NOT VALID (ERP returned error)")
            return False

        # Any other HTTP errors
        response.raise_for_status()

    except requests.RequestException as e:
        logging.error(f"[ERP CHECK ERROR] {employee_id}: {e}")
        return False



