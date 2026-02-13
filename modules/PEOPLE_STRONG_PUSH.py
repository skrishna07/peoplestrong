# ============================================================
# PEOPLESTRONG → ERP | FINAL PRODUCTION FILE
# ============================================================

from libraries import *
from modules.Helpers import *
from modules.Text_Field_Validator import *
from modules.Files_Field_Validator import *
from modules.Sql_Helper import *
from modules.Pending_Process import *
from modules.Csv_File_Handler import *
from api_handler.Ps_to_Erp_Requestor import send_to_erp
from modules.Document_Base64_Generator import get_candidate_document_links
from modules.SEND_EMAIL_SUMMARY import send_push_summary_email

# ============================================================
# CONFIG
# ============================================================

REPORT_FILE = "PeopleStrong_Master_Report.xlsx"


def build_erp_payload(row):
    payload = {

        # ================= PERSON =================
        "Person-title_id|disp": scalar(row.get("Title")),
        "Person-firstname": scalar(row.get("First Name")),
        "Person-middlename": scalar(row.get("Middle Name")),
        "Person-lastname": scalar(row.get("Last Name")),
        "Person-gender_id|disp": scalar(row.get("Gender")),
        "Person-mothername": scalar(row.get("Mothers Name")),
        "Person-birthdate": fmt_date(scalar(row.get("Birth Date"))),
        "Person-maritalstatus_id|disp": scalar(row.get("maritalstatus")),
        "Person-religion_id|disp": scalar(row.get("Religion")),
        "Person-nationality_id|disp": scalar(row.get("nationality")),
        "AltPhoneDetails": scalar(row.get("Alt Phone ISD")),
        "AltPhone": "971-" + scalar(row.get("Alt Phone")),
        "Email": scalar(row.get("Alt Email")),

        # ================= ADDRESS =================
        "Address-addresstype_id|disp": scalar(row.get("Address Type")),
        "Address-line1": scalar(row.get("AddressLine1")),
        "Address-line2": scalar(row.get("AddressLine2")),
        "Address-line3": scalar(row.get("AddressLine3")),
        "Address-zip": scalar(row.get("PIN")),
        "Address-city": scalar(row.get("City")),
        "Address-state": scalar(row.get("State")),
        "Address-country_id|disp": scalar(row.get("Country")),
        "LocalAddress": scalar(row.get("LocalAddress")),
        "HomeAddress": scalar(row.get("HomeAddress")),

        # ================= EDUCATION =================
        "Qualification-degreetype|disp": scalar(row.get("Edu Level")),
        "Qualification-studymajor": scalar(row.get("Specialization")),
        "Qualification-university": scalar(row.get("Institute Name")),
        "Qualification-datefrom": fmt_date(scalar(row.get("Start Date"))),
        "Qualification-dateto": fmt_date(scalar(row.get("End Date"))),
        "EmpCustomization-is_highest": scalar(row.get("Is Highest Qualification")),

        # ================= EMERGENCY =================
        "EmergyPhone": f'{row.get("Emergency Contact Number").lstrip("+").replace(" ", "")[:3]}-{row.get("Emergency Contact Number").lstrip("+").replace(" ", "")[3:]}',
        "EmergyPhoneDetails": scalar(row.get("Emergency Contact Relation")) + "-" + scalar(row.get("Emergency Contact Name")),

        # ================= ID =================
        "Passport-number": scalar(row.get("Passport-number")),
        "Passport-issuedate": fmt_date(scalar(row.get("Passport-issuedate"))),
        "Passport-issueplace": scalar(row.get("Passport-issueplace")),
        "Passport-expiry": fmt_date(scalar(row.get("Passport-expiry"))),

        "SponsorPassport-number": scalar(row.get("SponsorPassport-number")),
        "SponsorPassport-issuedate": fmt_date(scalar(row.get("SponsorPassport-issuedate"))),
        "SponsorPassport-issueplace": scalar(row.get("SponsorPassport-issueplace")),
        "SponsorPassport-expiry": fmt_date(scalar(row.get("SponsorPassport-expiry"))),

        "EmiratesID-number": scalar(row.get("EmiratesID-number")),
        "EmiratesID-issuingdate": fmt_date(scalar(row.get("EmiratesID-issuingdate"))),
        "EmiratesID-expirydate": fmt_date(scalar(row.get("EmiratesID-expirydate"))),

        "SponsorEmiratesID-number": scalar(row.get("SponsorEmiratesID-number")),
        "SponsorEmiratesID-issuingdate": fmt_date(scalar(row.get("SponsorEmiratesID-issuingdate"))),
        "SponsorEmiratesID-expirydate": fmt_date(scalar(row.get("SponsorEmiratesID-expirydate"))),

        "SponsorVisa-number": scalar(row.get("SponsorVisa-number")),
        "SponsorVisa-placeofissue": scalar(row.get("SponsorVisa-placeofissue")),
        "SponsorVisa-startdate": fmt_date(scalar(row.get("SponsorVisa-startdate"))),
        "SponsorVisa-enddate": fmt_date(scalar(row.get("SponsorVisa-enddate"))),

        "NOC-number": scalar(row.get("NOC-number")),
        "NOC-issuedate": fmt_date(scalar(row.get("NOC-issuedate"))),
        "NOC-expirydate": fmt_date(scalar(row.get("NOC-expirydate"))),

        "ILOEInsurance-empcompliance_id|disp": scalar(row.get("MedicalInsurance-number")),
        "MedicalInsurance-issuedate": fmt_date(scalar(row.get("MedicalInsurance-issuedate"))),
        "ILOEInsurance-expirydate": fmt_date(scalar(row.get("MedicalInsurance-expirydate"))),

        # ================= EMPLOYMENT =================
        "MOLOL-additionalclause": scalar(row.get("Contract Clause")),
        "EmployeeContract-legalstatus_id": scalar(row.get("Legal status")),
        "EmployeeContract-probationperiod": scalar(row.get("Probation")),
        "EmployeeContract-noticeperiod": scalar(row.get("Notice Period")),
        "EmployeeContract-empworkinghours": scalar(row.get("working hours")),
        "EmployeeContract-worktype|disp": scalar(row.get("work type")),
        "EmployeeContract-insuranceeligibiity_id|disp": scalar(row.get("insurance eligibility")),
        "EmployeeContract-airfareeligibility|disp": scalar(row.get("airfare eligibility")),
        "EmployeeContract-designation_id|disp": scalar(row.get("client designation")),
        "EmployeeContract-clientauth": scalar(row.get("client authorization details")),
        "EmployeeContract-startdate": fmt_date(scalar(row.get("Date of joining"))),
        "EmployeeContract-employeestatus_id|disp": scalar(row.get("Final Employment Status")),

        # ================= SALARY =================
        "SalaryHead_Basic": scalar(row.get("Salary_Basic")),
        "SalaryHead_HRA": scalar(row.get("Salary_HRA")),
        "SalaryHead_Food": scalar(row.get("Salary_Food")),
        "SalaryHead_Transport": scalar(row.get("Salary_Transport")),
        "SalaryHead_Telephone": scalar(row.get("Salary_Telephone")),
        "SalaryHead_Medical": scalar(row.get("Salary_Medical")),
        "SalaryHead_Electricity": scalar(row.get("Salary_Electricity")),
        "SalaryHead_Other Allowance": scalar(row.get("Salary_Other")),
        "SalaryHead_Variable Allowance": scalar(row.get("Salary_Variable")),
        "SalaryHead_Annual Leave Allowance": scalar(row.get("Salary_AnnualLeave")),
        "SalaryHead_Airfare Allowance": scalar(row.get("Salary_Airfare")),
        "Salary-startdate": fmt_date(scalar(row.get("Salary_EffectiveDate")))
    }

    payload = field_inspector(payload)
    logging.info("[PHASE 6] ERP Payload AFTER validation")
    return payload


def PS_to_ERP_Push(db_conn=None):
    logging.info("===== PEOPLESTRONG → ERP START =====")
    logging.info(f"Job Started At: {datetime.now()}")

    try:
        init_db()
    except Exception as e:
        print("Database Not Initialized")

    ssh, sftp = get_sftp_connection()
    logging.info("[PHASE 1] SFTP connected")

    dfs = load_csvs(sftp)
    master = build_master_dataframe(dfs)
    dump_df(master, "RPA_Master_File")

    push_data = []

    for _, r in master.iterrows():
        cid = r[JOIN_KEY]
        erpid = safe(r.get("ERPID"))

        logging.info("-" * 60)
        logging.info(f"[PHASE 5] Processing Candidate: {cid}")

        pending = fetch_pending_candidates(db_conn=db_conn)
        candidate_in_db = next((c for c in pending if c[0] == cid), None)

        if candidate_in_db:
            _, erpid_db, Text_payload, File_Payload, text_done, file_done, erp_done, last_status, comments = candidate_in_db
            logging.info(f"[RESUME] Candidate {cid} found in DB. Resuming from last state.")
        else:
            Text_payload = File_Payload = None
            text_done = file_done = erp_done = False

        if not erpid:
            logging.warning("[SKIP] ERPID missing — skipping candidate")
            push_data.append({
                "CandidateID": cid,
                "ERPID": "N/A",
                "status": "FAILED",
                "comments": "Missing ERPID — skipped"
            })
            continue

        print_peoplestrong_snapshot(r)

        try:
            if not Text_payload or not File_Payload:
                with ThreadPoolExecutor(max_workers=2) as executor:
                    future_text = executor.submit(build_erp_payload, r)
                    future_docs = executor.submit(get_candidate_document_links, cid)

                    Text_payload = future_text.result()
                    File_Payload = future_docs.result()

                save_to_queue(
                    candidate_id=cid,
                    erpid=erpid,
                    text_payload=Text_payload,
                    file_payload=File_Payload,
                    db_conn=db_conn
                )

            logging.info("[PHASE 6] Text payload and document links ready")
        except Exception as e:
            logging.error(f"[ERROR] Failed to prepare payload/docs for {cid}: {e}")
            save_to_queue(
                candidate_id=cid,
                erpid=erpid,
                status="FAILED",
                comments=f"Payload/Document prep failed: {str(e)}",
                db_conn=db_conn
            )
            push_data.append({
                "CandidateID": cid,
                "ERPID": erpid,
                "status": "FAILED",
                "comments": f"Payload/Document prep failed: {str(e)}"
            })
            continue

        try:
            if not erp_done:
                status, resp = send_to_erp(erpid, payload_data=Text_payload, file_data=File_Payload)
                bot_comment = "Synced Successfully" if status == "SUCCESS" else f"Failed: {resp}"

                save_to_queue(
                    candidate_id=cid,
                    erp_done=True if status == "SUCCESS" else False,
                    status=status,
                    comments=bot_comment,
                    db_conn=db_conn
                )

                logging.info(f"[PHASE 7] ERP Status={status} | ERPID={erpid}")
                print(f"[PHASE 7] ERP Response: {resp}")
            else:
                logging.info(f"[SKIP] ERP already done for {cid}")
                status = "SUCCESS"
                bot_comment = "Already Synced"
        except Exception as e:
            logging.error(f"[ERROR] ERP push failed for {erpid}: {e}")
            status = "FAILED"
            bot_comment = f"ERP push exception: {str(e)}"
            save_to_queue(
                candidate_id=cid,
                status=status,
                comments=bot_comment,
                db_conn=db_conn
            )

        push_data.append({
            "CandidateID": cid,
            "ERPID": erpid,
            "status": status,
            "comments": bot_comment
        })

    try:
        send_push_summary_email(push_data)
        logging.info(f"[SUMMARY] Sent summary email for {len(push_data)} candidates")
    except Exception as e:
        logging.error("Failed to send summary email: %s", str(e))

    ssh.close()
    logging.info("===== PROCESS COMPLETE =====")
