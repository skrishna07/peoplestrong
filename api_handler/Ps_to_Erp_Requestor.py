
from libraries import *
# def send_to_erp(erpid, payload):
#     conn = http.client.HTTPSConnection(ERP_HOST)
#     body = json.dumps({"data": {erpid: {"data": payload, "files": {}}}})
#     headers = {"auth": AUTH_TOKEN, "Content-Type": "application/json"}
#     conn.request("PUT", ERP_ENDPOINT, body=body, headers=headers)
#     res = conn.getresponse()
#     return res.status, res.read().decode()



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
                return True, ""
            else:
                # Map ERP errors into Excel
                error_str = "; ".join([f"{k}: {', '.join(v)}" for k, v in errors.items()])
                logging.warning(f"❌ Validation Failed for {erpid}: {error_str}")
                return False, error_str
        else:
            logging.error(f"❌ Server Rejected {res.status}: {res_data}")
            return False, f"Server Rejected {res.status}"

    except Exception as e:
        logging.error(f"❌ Connection Error: {str(e)}")
        return False, str(e)

