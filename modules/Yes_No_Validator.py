from libraries import *


PULL_TRACK_FILE = os.path.join("data_master", "pull", "pull_data_id_monitor.csv")
PULL_VALIDATOR_FILE = os.path.join("data_master", "pull", "Pull_Yes_or_No_Validator.csv")
PUSH_TRACK_FILE = os.path.join("data_master", "push", "push_data_id_monitor.csv")
PUSH_VALIDATOR_FILE = os.path.join("data_master", "push", "Push_Yes_or_No_Validator.csv")

PULL_HEADERS = [
    "CandidateID", "EmployeeCode", "ERP Valid", "Text Data Pulled", "personal-id",
    "IDType", "IDNumber", "NameOnDocument", "PlaceOfIssue", "DateofIssue", "ValidTill",
    "PassportNumber", "VisaIssueDate", "UIDNumber", "VisaNumber", "VisaType",
    "VisaExpiryDate", "VisaDesignation", "Joining-Insurance_Card",
    "Link-Joining-Insurance_Card", "Open-Joining-Insurance_Card", "Joining-Labour_Card",
    "Link-Joining-Labour_Card", "Open-Joining-Labour_Card", "Joining-MOL_Document",
    "Link-Joining-MOL_Document", "Open-Joining-MOL_Document",
    "Post_Joining-Typed_Emirates_Copy", "Link-Post_Joining-Typed_Emirates_Copy",
    "Open-Post_Joining-Typed_Emirates_Copy", "Post_Joining-Stamped_Visa",
    "Link-Post_Joining-Stamped_Visa", "Open-Post_Joining-Stamped_Visa", "All 5 Docs Pulled",
    "Final Status", "Pull Status", "DB Overall Status", "DB Pull Status", "DB Text Done",
    "DB File Done", "DB ERP Done", "Last Updated Date", "Last Updated Map File",
    "Last Modified", "Files Pulled", "Missing Docs", "ID / Text Data", "Comments",
    "DB Comments"
]

PUSH_SOURCE_HEADERS = [
    "Title", "First Name", "Middle Name", "Last Name", "Gender", "Mothers Name",
    "Birth Date", "maritalstatus", "Religion", "nationality", "Alt Phone ISD",
    "Alt Phone", "Alt Email", "Address Type", "AddressLine1", "AddressLine2",
    "AddressLine3", "PIN", "City", "State", "Country", "LocalAddress", "HomeAddress",
    "Edu Level", "Specialization", "Institute Name", "Start Date", "End Date",
    "Is Highest Qualification", "Emergency Contact Number", "Emergency Contact Relation",
    "Emergency Contact Name", "Passport-number", "Passport-issuedate", "Passport-issueplace",
    "Passport-expiry", "SponsorPassport-number", "SponsorPassport-issuedate",
    "SponsorPassport-issueplace", "SponsorPassport-expiry", "EmiratesID-number",
    "EmiratesID-issuingdate", "EmiratesID-expirydate", "SponsorEmiratesID-number",
    "SponsorEmiratesID-issuingdate", "SponsorEmiratesID-expirydate", "SponsorVisa-number",
    "SponsorVisa-placeofissue", "SponsorVisa-startdate", "SponsorVisa-enddate",
    "NOC-number", "NOC-issuedate", "NOC-expirydate", "MedicalInsurance-number",
    "MedicalInsurance-issuedate", "MedicalInsurance-expirydate", "Contract Clause",
    "Legal status", "Probation", "Notice Period", "working hours", "work type",
    "insurance eligibility", "airfare eligibility", "client designation",
    "client authorization details", "Date of joining", "Final Employment Status"
]

PUSH_REQUIRED_DOCS = [
    "Passport-scan", "EmpOLProcess-empexperienceletter", "Person-cv", "Person-photo",
    "EmiratesIDProcess-eidregform", "Qualification-certfile"
]

PUSH_HEADERS = [
    "CandidateID", "EmployeeCode", "ERP Valid", "Text Payload Ready", "Documents Ready",
    *PUSH_SOURCE_HEADERS,
    *PUSH_REQUIRED_DOCS,
    "ERP Pushed", "Final Status", "Push Status", "DB Overall Status", "DB ERP Done",
    "Last Updated Date", "Last Updated Map File", "Last Modified", "Comments", "DB Comments"
]

PULL_DOC_FIELD_MAP = {
    "ILOEInsurance-copy": (
        "Joining-Insurance_Card", "Link-Joining-Insurance_Card", "Open-Joining-Insurance_Card"
    ),
    "LaborContract-laborcardcopy": (
        "Joining-Labour_Card", "Link-Joining-Labour_Card", "Open-Joining-Labour_Card"
    ),
    "MOLOL-typedmolofferlcopy": (
        "Joining-MOL_Document", "Link-Joining-MOL_Document", "Open-Joining-MOL_Document"
    ),
    "EmiratesID-copy": (
        "Post_Joining-Typed_Emirates_Copy", "Link-Post_Joining-Typed_Emirates_Copy",
        "Open-Post_Joining-Typed_Emirates_Copy"
    ),
    "ResidenceVisaProcess-visastampreceipt": (
        "Post_Joining-Stamped_Visa", "Link-Post_Joining-Stamped_Visa", "Open-Post_Joining-Stamped_Visa"
    )
}

KEY_ALIASES = {
    "CandidateID": ["CandidateID", "candidate_id", "Candidate ID"],
    "EmployeeCode": ["EmployeeCode", "erpid", "ERPID"],
    "Last Updated Date": ["Last Updated Date", "batch_date"],
    "Last Updated Map File": ["Last Updated Map File", "mapping_file"],
    "Last Modified": ["Last Modified", "updated_at"],
    "DB Overall Status": ["DB Overall Status", "overall_status"],
    "DB Comments": ["DB Comments", "comments"],
}

STATUS_SUCCESS_SET = {"SUCCESS", "DONE", "COMPLETED", "SYNCED SUCCESSFULLY", "ALREADY SYNCED"}
TRUTHY_SET = {"1", "true", "yes", "y", "success"}
FALSY_MARKERS = {"", "-", "na", "n/a", "none", "null", "0"}
PUSH_COMMENT_EXACT_EXCLUSIONS = {
    "NO CANDIDATE DATA FOUND - PENDING FOR FUTURE PROCESSING",
    "ERP ID MISSING OR INVALID - WAITING",
    "ERP ID NOT YET GENERATED",
}
PUSH_COMMENT_TOKEN_EXCLUSIONS = (
    "PULL PENDING",
    "PULL SUCCESS",
    "PULL FAILED",
    "PULL SKIPPED",
    "REQUIRED DOCUMENT(S)",
    "REQUIRED DOCUMENTS IN ERP",
    "WILL RETRY NEXT RUN",
    "ERP ID NOT YET GENERATED IN SYSTEM",
    "MISSING REQUIRED DOCUMENTS IN ERP",
)
PULL_COMMENT_EXACT_EXCLUSIONS = {
    "NO CANDIDATE DATA FOUND - PENDING FOR FUTURE PROCESSING",
    "ERP ID MISSING OR INVALID - WAITING",
}


def _clean(value):
    if value is None:
        return ""
    return str(value).strip()


def _is_truthy(value):
    text = _clean(value).lower()
    return text not in FALSY_MARKERS and text in TRUTHY_SET


def _ensure_parent(file_path):
    os.makedirs(os.path.dirname(file_path), exist_ok=True)


def _read_rows(file_path):
    if not os.path.exists(file_path):
        return []
    with open(file_path, newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        return list(reader)


def _write_rows(file_path, headers, rows):
    _ensure_parent(file_path)
    with open(file_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=headers)
        writer.writeheader()
        for row in rows:
            writer.writerow({header: row.get(header, "") for header in headers})


def _remap_existing_row(row, headers):
    remapped = {header: "" for header in headers}
    lower_map = {_clean(key).lower(): key for key in row.keys()}

    for header in headers:
        if header in row:
            remapped[header] = row.get(header, "")
            continue

        aliases = KEY_ALIASES.get(header, [header])
        for alias in aliases:
            match = lower_map.get(_clean(alias).lower())
            if match:
                remapped[header] = row.get(match, "")
                break

    return remapped


def _ensure_schema(file_path, headers):
    _ensure_parent(file_path)
    if not os.path.exists(file_path):
        _write_rows(file_path, headers, [])
        return

    rows = _read_rows(file_path)
    if not rows:
        _write_rows(file_path, headers, [])
        return

    existing_headers = list(rows[0].keys())
    if existing_headers == headers:
        return

    remapped_rows = [_remap_existing_row(row, headers) for row in rows]
    _write_rows(file_path, headers, remapped_rows)


def _sanitize_push_tracking_file():
    if not os.path.exists(PUSH_TRACK_FILE):
        return

    rows = _read_rows(PUSH_TRACK_FILE)
    if not rows:
        return

    sanitized_rows = []
    changed = False
    for row in rows:
        sanitized_row = _sanitize_push_monitor_row(row)
        sanitized_rows.append(sanitized_row)
        if (
            sanitized_row.get("Comments", "") != row.get("Comments", "")
            or sanitized_row.get("DB Comments", "") != row.get("DB Comments", "")
        ):
            changed = True

    if changed:
        _write_rows(PUSH_TRACK_FILE, PUSH_HEADERS, sanitized_rows)


def _sanitize_pull_tracking_file():
    if not os.path.exists(PULL_TRACK_FILE):
        return

    rows = _read_rows(PULL_TRACK_FILE)
    if not rows:
        return

    sanitized_rows = []
    changed = False
    for row in rows:
        sanitized_row = _sanitize_pull_monitor_row(row)
        sanitized_rows.append(sanitized_row)
        if (
            sanitized_row.get("Comments", "") != row.get("Comments", "")
            or sanitized_row.get("DB Comments", "") != row.get("DB Comments", "")
        ):
            changed = True

    if changed:
        _write_rows(PULL_TRACK_FILE, PULL_HEADERS, sanitized_rows)


def ensure_tracking_files():
    _ensure_schema(PULL_TRACK_FILE, PULL_HEADERS)
    _ensure_schema(PULL_VALIDATOR_FILE, PULL_HEADERS)
    _ensure_schema(PUSH_TRACK_FILE, PUSH_HEADERS)
    _ensure_schema(PUSH_VALIDATOR_FILE, PUSH_HEADERS)
    _sanitize_pull_tracking_file()
    _sanitize_push_tracking_file()


def _candidate_from_row(row):
    for key in KEY_ALIASES["CandidateID"]:
        value = _clean(row.get(key))
        if value:
            return value
    return ""


def _upsert_row(file_path, headers, row):
    rows = _read_rows(file_path)
    target_id = _clean(row.get("CandidateID"))
    updated = False

    for idx, existing in enumerate(rows):
        if _candidate_from_row(existing) == target_id and target_id:
            rows[idx] = {header: row.get(header, "") for header in headers}
            updated = True
            break

    if not updated:
        rows.append({header: row.get(header, "") for header in headers})

    _write_rows(file_path, headers, rows)


def _get_row(file_path, candidate_id):
    target = _clean(candidate_id)
    if not target or not os.path.exists(file_path):
        return None

    for row in _read_rows(file_path):
        if _candidate_from_row(row) == target:
            return row
    return None


def get_push_tracking_row(candidate_id):
    row = _get_row(PUSH_TRACK_FILE, candidate_id)
    if not row:
        return None
    return _remap_existing_row(row, PUSH_HEADERS)


def get_pull_tracking_row(candidate_id):
    row = _get_row(PULL_TRACK_FILE, candidate_id)
    if not row:
        return None
    return _remap_existing_row(row, PULL_HEADERS)


def get_completed_pull_docs(candidate_id):
    row = get_pull_tracking_row(candidate_id) or {}
    docs_info = {}

    for doc_label, column_triplet in PULL_DOC_FIELD_MAP.items():
        value_col, link_col, _ = column_triplet
        file_name = _clean(row.get(value_col))
        file_path = _clean(row.get(link_col))
        if file_name or file_path:
            docs_info[doc_label] = {
                "filename": file_name,
                "path": file_path,
                "url": file_path,
            }

    return docs_info


def should_skip_push(candidate_id, mapping_file):
    row = _get_row(PUSH_TRACK_FILE, candidate_id)
    if not row:
        return False

    same_mapping = _clean(row.get("Last Updated Map File")) == _clean(mapping_file)
    final_status = _clean(row.get("Final Status") or row.get("Push Status") or row.get("DB Overall Status")).upper()
    already_pushed = _clean(row.get("ERP Pushed")).lower() == "yes"
    return already_pushed or (same_mapping and final_status in STATUS_SUCCESS_SET)


def should_skip_pull(candidate_id, mapping_file):
    row = _get_row(PULL_TRACK_FILE, candidate_id)
    if not row:
        return False

    same_mapping = _clean(row.get("Last Updated Map File")) == _clean(mapping_file)
    final_status = _clean(row.get("Final Status") or row.get("Pull Status") or row.get("DB Pull Status")).upper()
    all_docs_done = _clean(row.get("All 5 Docs Pulled")).lower() == "yes"
    return all_docs_done or (same_mapping and final_status in STATUS_SUCCESS_SET)


def _source_value(row, key):
    if row is None:
        return ""
    value = row.get(key, "")
    if pd.isna(value):
        return ""
    return str(value).strip()


def _looks_success(value):
    text = _clean(value).upper()
    return text in STATUS_SUCCESS_SET


def _normalize_comment_text(value):
    return _clean(value).replace("—", "-").replace("–", "-")


def _is_pull_only_push_comment(value):
    normalized = _normalize_comment_text(value).upper()
    if not normalized:
        return False
    if normalized in PUSH_COMMENT_EXACT_EXCLUSIONS:
        return True
    return any(token in normalized for token in PUSH_COMMENT_TOKEN_EXCLUSIONS)


def _sanitize_push_comment(value):
    text = _clean(value)
    if not text:
        return ""

    kept_lines = []
    seen = set()
    for line in re.split(r"[\r\n]+", text):
        cleaned_line = _clean(line)
        if not cleaned_line or _is_pull_only_push_comment(cleaned_line):
            continue
        dedupe_key = cleaned_line.lower()
        if dedupe_key in seen:
            continue
        kept_lines.append(cleaned_line)
        seen.add(dedupe_key)

    return "\n".join(kept_lines)


def _sanitize_push_monitor_row(row):
    sanitized = dict(row)
    sanitized_comments = _sanitize_push_comment(sanitized.get("Comments", ""))
    sanitized_db_comments = _sanitize_push_comment(sanitized.get("DB Comments", ""))
    sanitized["Comments"] = sanitized_comments
    sanitized["DB Comments"] = sanitized_db_comments or sanitized_comments
    return sanitized


def _sanitize_pull_comment(value):
    text = _clean(value)
    if not text:
        return ""

    kept_lines = []
    seen = set()
    for line in re.split(r"[\r\n]+", text):
        cleaned_line = _clean(line)
        normalized = _normalize_comment_text(cleaned_line).upper()
        if not cleaned_line or normalized in PULL_COMMENT_EXACT_EXCLUSIONS:
            continue
        dedupe_key = cleaned_line.lower()
        if dedupe_key in seen:
            continue
        kept_lines.append(cleaned_line)
        seen.add(dedupe_key)

    return "\n".join(kept_lines)


def _sanitize_pull_monitor_row(row):
    sanitized = dict(row)
    sanitized_comments = _sanitize_pull_comment(sanitized.get("Comments", ""))
    sanitized_db_comments = _sanitize_pull_comment(sanitized.get("DB Comments", ""))
    sanitized["Comments"] = sanitized_comments
    sanitized["DB Comments"] = sanitized_db_comments or sanitized_comments
    return sanitized


def _value_to_yes_no(header, value):
    text = _clean(value)
    lowered = text.lower()

    if header in {"ERP Valid", "Text Data Pulled", "Text Payload Ready", "Documents Ready", "All 5 Docs Pulled", "ERP Pushed"}:
        return "Yes" if lowered == "yes" or _is_truthy(text) else "No"

    if header.startswith("DB "):
        if header.endswith("Done"):
            return "Yes" if _is_truthy(text) else "No"
        return "Yes" if _looks_success(text) else "No"

    if header in {"Final Status", "Push Status", "Pull Status"}:
        return "Yes" if _looks_success(text) else "No"

    if header.startswith("Link-") or header.startswith("Open-"):
        return "Yes" if lowered not in FALSY_MARKERS else "No"

    if header in {"Comments", "DB Comments", "Files Pulled", "Missing Docs", "ID / Text Data", "Last Updated Date", "Last Updated Map File", "Last Modified"}:
        return "Yes" if lowered not in FALSY_MARKERS else "No"

    return "Yes" if lowered not in FALSY_MARKERS else "No"


def _to_validator_row(headers, monitor_row):
    return {header: _value_to_yes_no(header, monitor_row.get(header, "")) for header in headers}


def update_push_tracking(candidate_row=None, candidate_id=None, erpid=None, erp_valid=False,
                         mapping_file=None, batch_date=None, text_payload=None, file_payload=None,
                         status=None, db_overall_status=None, db_erp_done=None,
                         comments=None, db_comments=None):
    ensure_tracking_files()

    monitor_row = {header: "" for header in PUSH_HEADERS}
    cid = _clean(candidate_id) or _source_value(candidate_row or {}, "Candidate ID") or _source_value(candidate_row or {}, "CandidateID")
    existing_row = get_push_tracking_row(cid) or {}

    monitor_row["CandidateID"] = cid
    monitor_row["EmployeeCode"] = _clean(erpid)
    monitor_row["ERP Valid"] = "Yes" if erp_valid else "No"
    text_ready = bool(text_payload) or _clean(existing_row.get("Text Payload Ready")).lower() == "yes"
    docs_ready = bool(file_payload) or _clean(existing_row.get("Documents Ready")).lower() == "yes"
    monitor_row["Text Payload Ready"] = "Yes" if text_ready else "No"
    monitor_row["Documents Ready"] = "Yes" if docs_ready else "No"

    for header in PUSH_SOURCE_HEADERS:
        current_value = _source_value(candidate_row or {}, header)
        monitor_row[header] = current_value or _clean(existing_row.get(header))

    available_docs = set((file_payload or {}).keys()) if isinstance(file_payload, dict) else set()
    for doc_name in PUSH_REQUIRED_DOCS:
        already_completed = _clean(existing_row.get(doc_name)).lower() == "yes"
        monitor_row[doc_name] = "Yes" if doc_name in available_docs or already_completed else "No"

    final_status = _clean(status) or _clean(db_overall_status)
    monitor_row["ERP Pushed"] = "Yes" if _looks_success(final_status) else "No"
    monitor_row["Final Status"] = final_status
    monitor_row["Push Status"] = _clean(status)
    monitor_row["DB Overall Status"] = _clean(db_overall_status) or final_status
    monitor_row["DB ERP Done"] = 1 if (_is_truthy(db_erp_done) or _looks_success(final_status)) else 0
    monitor_row["Last Updated Date"] = _clean(batch_date)
    monitor_row["Last Updated Map File"] = _clean(mapping_file)
    monitor_row["Last Modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monitor_row["Comments"] = _sanitize_push_comment(comments)
    monitor_row["DB Comments"] = _sanitize_push_comment(db_comments) or monitor_row["Comments"]

    _upsert_row(PUSH_TRACK_FILE, PUSH_HEADERS, monitor_row)
    _upsert_row(PUSH_VALIDATOR_FILE, PUSH_HEADERS, _to_validator_row(PUSH_HEADERS, monitor_row))


def update_pull_tracking(candidate_id=None, employee_code=None, erp_valid=False, text_data_pulled=False,
                         docs_info=None, missing_docs=None, mapping_file=None, batch_date=None,
                         final_status=None, pull_status=None, db_overall_status=None,
                         db_pull_status=None, db_text_done=None, db_file_done=None,
                         db_erp_done=None, id_text_data=None, comments=None, db_comments=None):
    ensure_tracking_files()

    monitor_row = {header: "" for header in PULL_HEADERS}
    monitor_row["CandidateID"] = _clean(candidate_id)
    monitor_row["EmployeeCode"] = _clean(employee_code) or _clean(candidate_id)
    monitor_row["ERP Valid"] = "Yes" if erp_valid else "No"
    monitor_row["Text Data Pulled"] = "Yes" if text_data_pulled else "No"

    docs_info = docs_info or {}
    pulled_files = []
    for doc_label, column_triplet in PULL_DOC_FIELD_MAP.items():
        value_col, link_col, open_col = column_triplet
        doc_entry = docs_info.get(doc_label, {})
        file_name = _clean(doc_entry.get("filename"))
        file_path = _clean(doc_entry.get("path") or doc_entry.get("url"))
        monitor_row[value_col] = file_name
        monitor_row[link_col] = file_path
        monitor_row[open_col] = file_name
        if file_name:
            pulled_files.append(file_name)

    missing_docs = missing_docs or []
    monitor_row["All 5 Docs Pulled"] = "Yes" if not missing_docs and len(docs_info) == len(PULL_DOC_FIELD_MAP) else "No"
    monitor_row["Final Status"] = _clean(final_status)
    monitor_row["Pull Status"] = _clean(pull_status)
    monitor_row["DB Overall Status"] = _clean(db_overall_status)
    monitor_row["DB Pull Status"] = _clean(db_pull_status)
    monitor_row["DB Text Done"] = 1 if _is_truthy(db_text_done) or text_data_pulled else 0
    monitor_row["DB File Done"] = 1 if pulled_files or _is_truthy(db_file_done) else 0
    monitor_row["DB ERP Done"] = 1 if _is_truthy(db_erp_done) else 0
    monitor_row["Last Updated Date"] = _clean(batch_date)
    monitor_row["Last Updated Map File"] = _clean(mapping_file)
    monitor_row["Last Modified"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    monitor_row["Files Pulled"] = ", ".join(pulled_files) if pulled_files else "-"
    monitor_row["Missing Docs"] = ", ".join(missing_docs) if missing_docs else "-"
    monitor_row["ID / Text Data"] = _clean(id_text_data)
    monitor_row["Comments"] = _sanitize_pull_comment(comments)
    monitor_row["DB Comments"] = _sanitize_pull_comment(db_comments) or monitor_row["Comments"]

    _upsert_row(PULL_TRACK_FILE, PULL_HEADERS, monitor_row)
    _upsert_row(PULL_VALIDATOR_FILE, PULL_HEADERS, _to_validator_row(PULL_HEADERS, monitor_row))
