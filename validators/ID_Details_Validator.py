from libraries import *
from modules.Helpers import *
def normalize_id(df):
    df = df.copy()
    df["Date of Issue"] = pd.to_datetime(df["Date of Issue"], errors="coerce")
    # Keep the latest per Candidate ID + ID Type
    return df.sort_values(["Candidate ID", "ID Type", "Date of Issue"], ascending=[True, True, False]) \
             .drop_duplicates(["Candidate ID", "ID Type"])





def select_id_type(id_df, candidate_id):
    """
    Extract structured ID information for a given candidate.
    Handles:
    - Passport
    - Sponsor's Passport
    - Emirates ID
    - Sponsor's Emirates ID
    - Sponsor's Visa
    - NOC from the Sponsor
    - Medical Insurance Card

    Returns empty strings for any missing ID type.
    """

    # Initialize all fields
    row_data = {
        # Passport
        "Passport-number": "", "Passport-issuedate": "", "Passport-issueplace": "", "Passport-expiry": "",
        # Sponsor's Passport
        "SponsorPassport-number": "", "SponsorPassport-issuedate": "", "SponsorPassport-issueplace": "", "SponsorPassport-expiry": "",
        # Emirates ID
        "EmiratesID-number": "", "EmiratesID-issuingdate": "", "EmiratesID-expirydate": "",
        # Sponsor's Emirates ID
        "SponsorEmiratesID-number": "", "SponsorEmiratesID-issuingdate": "", "SponsorEmiratesID-expirydate": "",
        # Sponsor's Visa
        "SponsorVisa-number": "", "SponsorVisa-placeofissue": "", "SponsorVisa-startdate": "", "SponsorVisa-enddate": "",
        # NOC from Sponsor
        "NOC-number": "", "NOC-issuedate": "", "NOC-expirydate": "",
        # Medical Insurance Card
        "MedicalInsurance-number": "", "MedicalInsurance-issuedate": "", "MedicalInsurance-expirydate": ""
    }

    if id_df is None or id_df.empty:
        return pd.Series(row_data)

    candidate_rows = id_df[id_df["Candidate ID"] == candidate_id]
    if candidate_rows.empty:
        return pd.Series(row_data)

    for _, row in candidate_rows.iterrows():
        id_type = str(row.get("ID Type", "")).strip().lower()

        if "passport" == id_type:
            row_data.update({
                "Passport-number": scalar(row.get("ID Number")),
                "Passport-issuedate": fmt_date(scalar(row.get("Date of Issue"))),
                "Passport-issueplace": scalar(row.get("Place of Issue")),
                "Passport-expiry": fmt_date(scalar(row.get("Valid Till")))
            })
        elif "sponsor's passport" in id_type:
            row_data.update({
                "SponsorPassport-number": scalar(row.get("ID Number")),
                "SponsorPassport-issuedate": fmt_date(scalar(row.get("Date of Issue"))),
                "SponsorPassport-issueplace": scalar(row.get("Place of Issue")),
                "SponsorPassport-expiry": fmt_date(scalar(row.get("Valid Till")))
            })
        elif "emirates id" == id_type:
            row_data.update({
                "EmiratesID-number": scalar(row.get("ID Number")),
                "EmiratesID-issuingdate": fmt_date(scalar(row.get("Date of Issue"))),
                "EmiratesID-expirydate": fmt_date(scalar(row.get("Valid Till")))
            })
        elif "sponsor's emirates id" in id_type:
            row_data.update({
                "SponsorEmiratesID-number": scalar(row.get("ID Number")),
                "SponsorEmiratesID-issuingdate": fmt_date(scalar(row.get("Date of Issue"))),
                "SponsorEmiratesID-expirydate": fmt_date(scalar(row.get("Valid Till")))
            })
        elif "sponsor's visa" in id_type:
            row_data.update({
                "SponsorVisa-number": scalar(row.get("ID Number")),
                "SponsorVisa-placeofissue": scalar(row.get("Place of Issue")),
                "SponsorVisa-startdate": fmt_date(scalar(row.get("Date of Issue"))),
                "SponsorVisa-enddate": fmt_date(scalar(row.get("Valid Till")))
            })
        elif "noc" in id_type:
            row_data.update({
                "NOC-number": scalar(row.get("ID Number")),
                "NOC-issuedate": fmt_date(scalar(row.get("Date of Issue"))),
                "NOC-expirydate": fmt_date(scalar(row.get("Valid Till")))
            })
        elif "medical insurance card" in id_type:
            row_data.update({
                "ILOEInsurance-empcompliance_id|disp": scalar(row.get("ID Number")),
                "MedicalInsurance-issuedate": fmt_date(scalar(row.get("Date of Issue"))),
                "ILOEInsurance-expirydate": fmt_date(scalar(row.get("Valid Till")))
            })

    return pd.Series(row_data)

