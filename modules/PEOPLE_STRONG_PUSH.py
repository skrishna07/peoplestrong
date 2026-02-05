# --- CUSTOM MODULE IMPORTS ---
from libraries import *
from modules.helpers import *
from modules.Text_Field_Validator import *
from modules.Files_Field_Validator import *
from modules.Sql_Helper import *
from modules.Pending_Process import *


# --- EXCEL REPORTING UTILITY ---
def append_to_validation_excel(data_row, file_path="Sync_Master_Report.xlsx"):
    """Appends mapping data to the master report with a fixed column order."""
    column_order = [
        "Sync_Timestamp", "ERP_ID", "Candidate_ID", "Sync_Status", "Files_Count",
        "Person-addresstype", "Person-currentaddress", "Person-addressline2",
        "Person-addressline3", "Person-pincode", "Person-city", "Person-district",
        "Person-state", "Person-country", "EmpCustomization-edu_level",
        "EmpCustomization-specialization", "EmpCustomization-institute",
        "EmpCustomization-startdate", "EmpCustomization-enddate",
        "EmpCustomization-is_highest", "Person-title", "Person-middlename",
        "Person-gender_id|disp", "Person-mothername", "Person-maritalstatus_id|disp",
        "Person-religion_id|disp", "Person-nationality_id|disp", "AltPhoneDetails",
        "AltPhone", "Person-emergencycontactisd", "EmployeeContract-clause",
        "EmployeeContract-clientauth", "EmployeeContract-doj",
        "EmployeeContract-legalstatus_id", "Person-emergencycontactnumber",
        "Person-emergencycontactrelation", "Person-emergencycontactname",
        "EmpCustomization-id_number", "EmpCustomization-id_type",
        "EmpCustomization-placeofissue", "EmpCustomization-dateofissue",
        "EmpCustomization-valid_till", "SalaryHead-Basic", "Salary-total",
        "Salary-effectivedate", "All_File_Names", "Time_Taken", "Upload_Errors"
    ]

    try:
        df_new = pd.DataFrame([data_row]).reindex(columns=column_order)

        if not os.path.exists(file_path):
            df_new.to_excel(file_path, index=False, engine='openpyxl')
        else:
            with pd.ExcelWriter(file_path, engine='openpyxl', mode='a', if_sheet_exists='overlay') as writer:
                existing_df = pd.read_excel(file_path)
                start_row = len(existing_df) + 1
                df_new.to_excel(writer, index=False, header=False, startrow=start_row)

        logging.info(f"[EXCEL] Data logged correctly for ERPID: {data_row.get('ERP_ID')}")
    except Exception as e:
        logging.error(f"[EXCEL] Error appending data: {e}")


def generate_curl(erpid, payload_json, headers):
    return f"""
curl -X PUT https://{ERP_HOST}{ERP_ENDPOINT} \\
  -H "auth: {headers['auth']}" \\
  -H "Content-Type: application/json" \\
  -d '{payload_json}'
""".strip()


def send_request_to_erp(erpid, payload_data, file_data=None):
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


# --- API TRANSPORT LAYER ---
def PS_to_ERP_Push():
    logging.info("="*60)
    logging.info(">>> STARTING PEOPLESTRONG TO ERP DIGITAL RELAY <<<")
    logging.info("="*60)

    init_db()
    # process_pending_queue()

    ssh = None
    try:
        # --- PHASE 2: SFTP EXTRACTION ---
        logging.info("[PHASE 2] Connecting to SFTP for data extraction...")
        ssh, sftp = get_sftp_connection()
        all_files = sftp.listdir(IMPORT_DIR)

        data_frames = {}
        prefixes = ['CandidateData', 'Mapping', 'CandidateContact', 'CandidateSalaryData',
                    'CandidateEducation', 'CandidateIDDetails', 'CandidateEmergencyContact']

        for prefix in prefixes:
            matches = [f for f in all_files if f.startswith(prefix) and f.endswith('.csv')]
            if matches:
                latest_file = sorted(matches, reverse=True)[0]
                logging.info(f"[PHASE 2] Reading latest {prefix}: {latest_file}")
                with sftp.open(f"{IMPORT_DIR}/{latest_file}", "rb") as f:
                    df = pd.read_csv(io.BytesIO(f.read()), sep='|', dtype=str)
                    df.columns = df.columns.str.strip()
                    if prefix == 'Mapping':
                        df = df.rename(columns={'PeopleStrongID': JOIN_KEY})
                    data_frames[prefix] = df

        # --- PHASE 3: DATA MERGING & CLEANING ---
        if 'CandidateData' not in data_frames:
            logging.error("[PHASE 3] Critical: CandidateData.csv missing. Aborting.")
            return

        logging.info("[PHASE 3] Merging all CSV data into Master DataFrame...")
        master_df = data_frames['CandidateData']
        for key in [k for k in data_frames.keys() if k != 'CandidateData']:
            if JOIN_KEY in data_frames[key].columns:
                master_df = pd.merge(master_df, data_frames[key], on=JOIN_KEY, how='left')

        master_df['ERPID'] = master_df['ERPID'].astype(str).str.split('.').str[0]
        final_df = master_df[master_df['ERPID'].notnull() & (master_df['ERPID'] != 'nan')].drop_duplicates(subset=['ERPID'])
        logging.info(f"[PHASE 3] Found {len(final_df)} valid candidates to process.")

        # --- PHASE 4: TRANSFORMATION & DELIVERY ---
        logging.info("[PHASE 4] Loading mapping configurations...")
        text_mapping = load_text_mapping_config()

        for _, row in final_df.iterrows():
            erpid = str(row.get('ERPID'))
            candidate_folder = row.get('Candidate ID')
            logging.info(f"--- Processing ERPID: {erpid} ---")

            validation_row = {
                "Sync_Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "ERP_ID": erpid,
                "Candidate_ID": candidate_folder
            }

            # 1. Prepare Text Fields
            payload_text = {}
            for ps_header, erp_key in text_mapping.items():
                val = row.get(ps_header)
                if pd.notnull(val) and str(val).strip() != "":
                    val = str(val).strip()
                    if any(x in erp_key.lower() for x in ["date", "birth", "doj", "till", "expiry"]):
                        try: val = pd.to_datetime(val).strftime('%Y-%m-%d')
                        except: pass
                    elif any(x in erp_key.lower() for x in ["total", "basic", "amount"]):
                        try: val = "{:.4f}".format(float(val))
                        except: val = "0.0000"
                    payload_text[erp_key] = val
                    validation_row[erp_key] = val
                else:
                    validation_row[erp_key] = "N/A"

            print(f"[DEBUG] Raw PeopleStrong fields for ERPID {erpid}:")
            print({ps_header: row.get(ps_header) for ps_header in text_mapping.keys()})

            # 2. Fetch Files
            logging.info(f"[PHASE 4] Fetching documents for {erpid}...")
            file_payload = get_candidate_document_links(candidate_folder)
            validation_row["Files_Count"] = len(file_payload)
            validation_row["All_File_Names"] = ", ".join(file_payload.keys()) if file_payload else "N/A"

            # 3. Validate Fields
            field_validator_returned_text = field_inspector(payload_text=payload_text)

            # 4. Send to ERP
            start_time = time.time()
            success, error_str = send_request_to_erp(erpid, field_validator_returned_text, file_payload)
            end_time = time.time()
            validation_row["Time_Taken"] = round(end_time - start_time, 2)
            validation_row["Upload_Errors"] = error_str

            if success:
                remove_from_queue(erpid)
                validation_row["Sync_Status"] = "SUCCESS"
                logging.info(f"✅ ERPID {erpid} Sync Complete.")
            else:
                combined_queue_payload = {"data": payload_text, "files": file_payload}
                save_to_queue(erpid, combined_queue_payload)
                validation_row["Sync_Status"] = "FAILED/QUEUED"
                logging.warning(f"⚠️ ERPID {erpid} Sync Failed.")

            append_to_validation_excel(validation_row)

    except Exception as e:
        logging.critical(f"SYSTEM FATAL ERROR: {str(e)}")
        logging.error(traceback.format_exc())
    finally:
        if ssh:
            ssh.close()
            logging.info("[CLEANUP] SFTP connection closed.")
        logging.info("="*60)
        logging.info(">>> DIGITAL RELAY CYCLE FINISHED <<<")
        logging.info("="*60)
