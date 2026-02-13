from libraries import *
from validators.Education_Validator import normalize_education
from validators.ID_Details_Validator import normalize_id,select_id_type
from validators.Salary_Validator import normalize_salary
from validators.Contact_Validator import select_primary_address,build_address_payloads



def latest_file(files, prefix):
    pat = re.compile(rf"{prefix}_(\d{{8}})_(\d{{6}})\.csv")
    best, best_dt = None, None
    for f in files:
        m = pat.match(f)
        if m:
            dt = datetime.strptime(m.group(1) + m.group(2), "%d%m%Y%H%M%S")
            if not best_dt or dt > best_dt:
                best, best_dt = f, dt
    return best



def robust_pipe_reader(file_obj):
    data = []
    if isinstance(file_obj, str):
        f = open(file_obj, 'r', encoding='utf-8')
    else:
        f = io.TextIOWrapper(file_obj, encoding='utf-8')
    
    with f as reader:
        csv_reader = csv.reader(reader, delimiter='|', quotechar='"', escapechar='\\')
        for i, row in enumerate(csv_reader):
            while len(row) < 12:
                row.append('')
            if len(row) > 12:
                row = row[:12]
            data.append(row)
    
    return pd.DataFrame(data[1:], columns=data[0], dtype=str)


def load_csvs(sftp):
    prefixes = [
        "CandidateData",
        "CandidateContact",
        "CandidateEducation",
        "CandidateEmergencyContact",
        "CandidateIDDetails",
        "CandidateSalaryData",
        "Mapping"
    ]

    files = sftp.listdir(IMPORT_DIR)
    dfs = {}

    logging.info("[PHASE 2] Loading PeopleStrong CSVs")

    for p in prefixes:
        f = latest_file(files, p)
        if not f:
            raise RuntimeError(f"Missing mandatory CSV: {p}")

        sftp_path = f"{IMPORT_DIR}/{f}"
        logging.info(f"[PHASE 2] Reading file: {f} → {sftp_path}")

        if p == "CandidateContact":
            with sftp.open(sftp_path, "rb") as fh:
                df = robust_pipe_reader(fh)
        else:
            with sftp.open(sftp_path, "rb") as fh:
                df = pd.read_csv(io.BytesIO(fh.read()), sep="|", dtype=str)

        df.columns = df.columns.str.strip()

        if p == "Mapping":
            df = df.rename(columns={"PeopleStrongID": JOIN_KEY})

        if JOIN_KEY not in df.columns:
            raise RuntimeError(f"{p} missing {JOIN_KEY}")

        dfs[p] = df
        logging.info(f"[PHASE 2] {p} rows loaded: {len(df)}")

    logging.info("[PHASE 2] All CSV files loaded successfully")
    return dfs


def dump_df(df, name):
    os.makedirs("debug_dump", exist_ok=True)
    path = f"debug_dump/{name}.csv"
    df.to_csv(path, index=False)
    print(f"[DEBUG] Saved {name} → {path} ({len(df)} rows)")




# def build_master_dataframe(dfs):
#     """
#     Builds the master DataFrame by merging all relevant candidate data.
#     Normalizes education, ID, and salary.
#     Integrates primary address and main ID details directly into the master.
#     """
#     logging.info("[PHASE 3] Normalizing datasets")

#     # ---------------- EDUCATION ----------------
#     edu_df = dfs.get("CandidateEducation")
#     if edu_df is not None:
#         edu_df = normalize_education(edu_df)
#         logging.info(f"[PHASE 3] Education normalized: {len(edu_df)} rows")
#     else:
#         edu_df = pd.DataFrame(columns=[JOIN_KEY, "Edu Level", "Specialization",
#                                        "Institute Name", "Start Date", "End Date", "Is Highest Qualification"])

#     # ---------------- ID DETAILS ----------------
#     id_df = dfs.get("CandidateIDDetails")
#     if id_df is not None:
#         id_df = normalize_id(id_df)
#         logging.info(f"[PHASE 3] ID details normalized: {len(id_df)} rows")
#         # Pick main ID for each candidate
#         id_main_df = id_df.groupby(JOIN_KEY).apply(lambda grp: select_id_type(grp, grp.name))
#         id_main_df = id_main_df.reset_index(drop=True)

#     else:
#         id_df = pd.DataFrame(columns=[JOIN_KEY])

#     # ---------------- SALARY ----------------
#     sal_df = dfs.get("CandidateSalaryData")
#     if sal_df is not None:
#         sal_df = normalize_salary(sal_df)
#         logging.info(f"[PHASE 3] Salary normalized: {len(sal_df)} rows")
#     else:
#         sal_df = pd.DataFrame(columns=[JOIN_KEY])

#     # ---------------- MERGE CORE DATA ----------------
#     logging.info("[PHASE 4] Merging core datasets into master DataFrame")
#     master = dfs["CandidateData"].copy()
#     master = (
#         master
#         .merge(edu_df, on=JOIN_KEY, how="left")
#         .merge(dfs.get("CandidateEmergencyContact", pd.DataFrame(columns=[JOIN_KEY])), on=JOIN_KEY, how="left")
#         .merge(id_df, on=JOIN_KEY, how="left")
#         .merge(sal_df, on=JOIN_KEY, how="left")
#         .merge(dfs.get("Mapping", pd.DataFrame(columns=[JOIN_KEY])), on=JOIN_KEY, how="inner")
#     )

#     # ---------------- PRIMARY ADDRESS ----------------
#     address_df = dfs.get("CandidateContact")
#     if address_df is not None and not address_df.empty:
#         primary_address_rows = address_df.groupby(JOIN_KEY).apply(lambda grp: select_primary_address(grp, grp.name))
#         master = master.merge(primary_address_rows.reset_index(drop=True), on=JOIN_KEY, how="left")
#         logging.info(f"[PHASE 4] Primary addresses merged: {len(primary_address_rows)} rows")
#     else:
#         logging.warning("[PHASE 4] CandidateContact CSV missing or empty")

#     # ---------------- FINAL MASTER READY ----------------
#     logging.info(f"[PHASE 4] Master DataFrame ready: {len(master)} rows")
#     return master



# def build_master_dataframe(dfs):
#     """
#     Builds the master DataFrame by merging all relevant candidate data.
#     Only candidates present in the Mapping CSV will be included.
#     Normalizes education, ID, and salary.
#     Integrates primary address and main ID details directly into the master.
#     """
#     logging.info("[PHASE 3] Normalizing datasets")

#     # ---------------- EDUCATION ----------------
#     edu_df = dfs.get("CandidateEducation")
#     if edu_df is not None:
#         edu_df = normalize_education(edu_df)
#         logging.info(f"[PHASE 3] Education normalized: {len(edu_df)} rows")
#     else:
#         edu_df = pd.DataFrame(
#             columns=[
#                 JOIN_KEY, "Edu Level", "Specialization",
#                 "Institute Name", "Start Date", "End Date", "Is Highest Qualification"
#             ]
#         )

#     # ---------------- ID DETAILS ----------------
#     id_df = dfs.get("CandidateIDDetails")
#     if id_df is not None:
#         id_df = normalize_id(id_df)
#         logging.info(f"[PHASE 3] ID details normalized: {len(id_df)} rows")
#         # Pick main ID for each candidate
#         id_main_df = (
#             id_df.groupby(JOIN_KEY)
#             .apply(lambda grp: select_id_type(grp, grp.name))
#             .reset_index(drop=False)
#         )
#         logging.info(f"[PHASE 3] Main ID selected for candidates: {len(id_main_df)} rows")
#     else:
#         id_main_df = pd.DataFrame(columns=[JOIN_KEY])

#     # ---------------- SALARY ----------------
#     sal_df = dfs.get("CandidateSalaryData")
#     if sal_df is not None:
#         sal_df = normalize_salary(sal_df)
#         logging.info(f"[PHASE 3] Salary normalized: {len(sal_df)} rows")
#     else:
#         sal_df = pd.DataFrame(columns=[JOIN_KEY])

#     # ---------------- MAPPING ----------------
#     mapping_df = dfs.get("Mapping")
#     if mapping_df is None or mapping_df.empty:
#         raise RuntimeError("Mapping CSV is missing or empty!")
#     # Ensure column names are standardized
#     mapping_df = mapping_df.rename(columns={"PeopleStrongID": JOIN_KEY})
#     logging.info(f"[PHASE 3] Mapping loaded: {len(mapping_df)} rows")

#     # ---------------- MERGE CORE DATA ----------------
#     logging.info("[PHASE 4] Merging core datasets into master DataFrame")

#     # Start with CandidateData
#     master = dfs["CandidateData"].copy()
#     # STRICTLY include only candidates in Mapping
#     master = master.merge(mapping_df, on=JOIN_KEY, how="inner")

#     # Merge other optional datasets
#     master = (
#         master
#         .merge(edu_df, on=JOIN_KEY, how="left")
#         .merge(dfs.get("CandidateEmergencyContact", pd.DataFrame(columns=[JOIN_KEY])), on=JOIN_KEY, how="left")
#         .merge(id_main_df, on=JOIN_KEY, how="left")
#         .merge(sal_df, on=JOIN_KEY, how="left")
#     )

#     # ---------------- PRIMARY ADDRESS ----------------
#     address_df = dfs.get("CandidateContact")
#     if address_df is not None and not address_df.empty:
#         primary_address_rows = (
#             address_df.groupby(JOIN_KEY)
#             .apply(lambda grp: select_primary_address(grp, grp.name))
#             .reset_index(drop=True)
#         )
#         master = master.merge(primary_address_rows, on=JOIN_KEY, how="left")
#         logging.info(f"[PHASE 4] Primary addresses merged: {len(primary_address_rows)} rows")
#     else:
#         logging.warning("[PHASE 4] CandidateContact CSV missing or empty")

#     # ---------------- REMOVE DUPLICATES ----------------
#     master = master.drop_duplicates(subset=[JOIN_KEY])
#     logging.info(f"[PHASE 4] Master DataFrame ready: {len(master)} rows")

#     return master



def build_master_dataframe(dfs):
    """
    Builds the master DataFrame by merging only relevant candidate data.
    Only candidates present in the Mapping CSV will be included.
    Normalizes education, ID, and salary.
    Integrates primary address and main ID details directly into the master.
    """
    logging.info("[PHASE 3] Starting master DataFrame build")

    # ---------------- MAPPING ----------------
    mapping_df = dfs.get("Mapping")
    if mapping_df is None or mapping_df.empty:
        raise RuntimeError("Mapping CSV is missing or empty!")

    mapping_df = mapping_df.rename(columns={"PeopleStrongID": JOIN_KEY})
    candidate_ids = mapping_df[JOIN_KEY].astype(str).str.strip().tolist()
    logging.info(f"[PHASE 3] Mapping loaded: {len(mapping_df)} candidates")
    print(f"[INFO] Today we got {len(mapping_df)} candidates in Mapping CSV")
    print("\n[INFO] CandidateID | ERP ID")
    for _, row in mapping_df.iterrows():
        print(f"{row[JOIN_KEY]} | {row.get('ERP', 'N/A')}")

    # ---------------- HELPER: FILTER CANDIDATES ----------------
    def filter_candidates(df, name):
        if df is None or df.empty:
            print(f"[INFO] No records found for {name}")
            return pd.DataFrame(columns=[JOIN_KEY])
        df[JOIN_KEY] = df[JOIN_KEY].astype(str).str.strip()
        filtered = df[df[JOIN_KEY].isin(candidate_ids)].copy()
        print(f"[INFO] {len(filtered)} {name} records match the Mapping candidates")
        return filtered

    # ---------------- FILTER & NORMALIZE DATA ----------------
    candidate_data = filter_candidates(dfs.get("CandidateData"), "CandidateData")

    edu_df = filter_candidates(dfs.get("CandidateEducation"), "CandidateEducation")
    if not edu_df.empty:
        edu_df = normalize_education(edu_df)
        print(f"[INFO] Education normalized for {len(edu_df)} records")

    id_df = filter_candidates(dfs.get("CandidateIDDetails"), "CandidateIDDetails")
    if not id_df.empty:
        id_df = normalize_id(id_df)
        print(f"[INFO] ID details normalized for {len(id_df)} records")
        id_main_df = (
    id_df.groupby(JOIN_KEY, group_keys=False)  # prevents adding extra index
    .apply(lambda grp: select_id_type(grp, grp.name))
    .reset_index(drop=False)
)

        print(f"[INFO] Main IDs selected for {len(id_main_df)} candidates")
    else:
        id_main_df = pd.DataFrame(columns=[JOIN_KEY])
        print(f"[INFO] No ID details to process today")

    sal_df = filter_candidates(dfs.get("CandidateSalaryData"), "CandidateSalaryData")
    if not sal_df.empty:
        sal_df = normalize_salary(sal_df)
        print(f"[INFO] Salary normalized for {len(sal_df)} records")

    address_df = filter_candidates(dfs.get("CandidateContact"), "CandidateContact")

    emergency_df = filter_candidates(dfs.get("CandidateEmergencyContact"), "CandidateEmergencyContact")

    # ---------------- MERGE CORE DATA ----------------
    print("[INFO] Merging core datasets into master DataFrame")
    master = candidate_data.merge(mapping_df, on=JOIN_KEY, how="inner")

    master = (
        master
        .merge(edu_df, on=JOIN_KEY, how="left")
        .merge(emergency_df, on=JOIN_KEY, how="left")
        .merge(id_main_df, on=JOIN_KEY, how="left")
        .merge(sal_df, on=JOIN_KEY, how="left")
    )

    # ---------------- PRIMARY ADDRESS ----------------
    if address_df is not None and not address_df.empty:
        primary_address_rows = (
            address_df.groupby(JOIN_KEY)
            .apply(lambda grp: select_primary_address(grp, grp.name))
            .reset_index(drop=True)
        )
        master = master.merge(primary_address_rows, on=JOIN_KEY, how="left")
        print(f"[INFO] Primary addresses merged for {len(primary_address_rows)} candidates")
    else:
        print("[INFO] CandidateContact CSV missing or empty")

    # ---------------- REMOVE DUPLICATES ----------------
    master = master.drop_duplicates(subset=[JOIN_KEY])
    print(f"[INFO] Master DataFrame ready with {len(master)} candidates today")

    return master

