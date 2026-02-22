from libraries import *
from modules.Helpers import *
from modules.Text_Field_Validator import field_inspector
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
        "Address-country_id|disp": full_country_name(scalar(row.get("Country"))),
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
        "EmergyPhone": (lambda x: f"{x[:3]}-{x[3:]}" if x else "")(scalar(row.get("Emergency Contact Number")).lstrip("+").replace(" ", "")),
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
        "EmployeeContract-employeestatus_id|disp": scalar(row.get("Final Employment Status"))        
    }

    payload = field_inspector(payload)
    logging.info("[PHASE 6] ERP Payload AFTER validation")
    return payload
