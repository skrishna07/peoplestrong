from libraries import *

def normalize_education(df):
    df = df.copy()

    # Ensure required columns exist
    required_cols = ["Candidate ID", "Edu Level", "Specialization", "Institute Name", "Start Date", "End Date", "Is Highest Qualification"]
    for col in required_cols:
        if col not in df.columns:
            df[col] = ""

    # Convert dates safely
    df["End Date"] = pd.to_datetime(df["End Date"], errors="coerce")
    df["Start Date"] = pd.to_datetime(df["Start Date"], errors="coerce")

    # Rank: highest qualification first
    df["rank"] = df["Is Highest Qualification"].apply(lambda x: 1 if str(x).strip().lower() == "yes" else 2)

    # Sort by rank, End Date desc, Start Date desc, then Institute Name (tie-breaker)
    df = df.sort_values(["rank", "End Date", "Start Date", "Institute Name"], ascending=[True, False, False, True])

    # Pick first row per candidate
    df = df.drop_duplicates("Candidate ID", keep="first")

    # Drop helper column
    df = df.drop(columns=["rank"])

    return df
