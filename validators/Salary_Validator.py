from libraries import *
def normalize_salary(df):
    SALARY_MAP = {
        "Basic": "Salary_Basic",
        "HRA": "Salary_HRA",
        "Food Allowanace": "Salary_Food",
        "Transport": "Salary_Transport",
        "Telephone": "Salary_Telephone",
        "Other Allowance": "Salary_Other",
        "Fixed": "Salary_Fixed",
        "Total Salary (A)": "Salary_Total",
        "Medical": "Salary_Medical",
        "Electricity": "Salary_Electricity",
        "Annual leave allowance": "Salary_AnnualLeave",
        "Airfare allowance": "Salary_Airfare",

        # ----- VARIABLE -----
        "Variable": "Salary_Variable",
        "Variable allowance": "Salary_Variable"

    }
    df[JOIN_KEY] = (
    df[JOIN_KEY]
    .astype(str)
    .str.strip()
    .str.replace("\u00a0", "", regex=False)
)

    rows = []
    for cid, g in df.groupby(JOIN_KEY):
        row = {JOIN_KEY: cid}
        for _, r in g.iterrows():
            col = SALARY_MAP.get(r.get("PayCodeName"))
            if col:
                row[col] = r.get("Amount")
                row["Salary_EffectiveDate"] = r.get("EffectiveDate")
        rows.append(row)

    return pd.DataFrame(rows)
