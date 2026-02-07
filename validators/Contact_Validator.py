from libraries import *
from modules.Helpers import *




def select_primary_address(address_df, candidate_id):
    """
    Return a single row (pd.Series) with both Local and Home addresses as concatenated strings.
    Fields:
        ["Candidate ID", "Address Type", "AddressLine1", "AddressLine2",
        "AddressLine3", "PIN", "City", "District", "State", "Country",
        "Mobile No", "LocalAddress", "HomeAddress"]
    """

    keys = [
        "Address Type", "AddressLine1", "AddressLine2",
        "AddressLine3", "PIN", "City", "District", "State",
        "Country", "Mobile No"
    ]

    # Initialize empty row
    row_data = {k: "" for k in keys}
    row_data["Candidate ID"] = candidate_id
    row_data["LocalAddress"] = ""
    row_data["HomeAddress"] = ""

    if address_df is None or address_df.empty:
        return pd.Series(row_data)

    address_df = address_df.copy()
    address_df.columns = address_df.columns.str.strip()
    address_df["Address Type"] = (
        address_df["Address Type"]
        .astype(str)
        .str.strip()
        .str.replace("\u00a0", "", regex=False)
    )

    # Separate Local and Home addresses
    local_df = address_df[address_df["Address Type"].str.contains("Local", case=False)]
    home_df = address_df[address_df["Address Type"].str.contains("Home", case=False)]

    def concat_address(row):
        """Combine non-empty address fields into a single string"""
        if row is None or row.empty:
            return ""
        parts = [
            row.get("AddressLine1", ""),
            row.get("AddressLine2", ""),
            row.get("AddressLine3", ""),
            row.get("City", ""),
            row.get("District", ""),
            row.get("State", ""),
            row.get("Country", ""),
            row.get("PIN", "")
        ]
        return ", ".join([str(p).strip() for p in parts if p and str(p).strip()])

    # Fill Local address first (pick first if multiple)
    local_row = local_df.iloc[0] if not local_df.empty else None
    home_row = home_df.iloc[0] if not home_df.empty else None

    if local_row is not None:
        for k in keys:
            row_data[k] = local_row.get(k, "")  # Default main fields use Local first
        row_data["LocalAddress"] = concat_address(local_row)

    if home_row is not None:
        row_data["HomeAddress"] = concat_address(home_row)

    return pd.Series(row_data)


def build_address_payloads(addr_df):
    payloads = []

    for _, r in addr_df.iterrows():
        payloads.append({
            "Address-addresstype_id|disp": safe(r.get("Address Type")),
            "Address-line1": safe(r.get("AddressLine1")),
            "Address-line2": safe(r.get("AddressLine2")),
            "Address-line3": safe(r.get("AddressLine3")),
            "Address-zip": safe(r.get("PIN")),
            "Address-city": safe(r.get("City")),
            "Address-district": safe(r.get("District")),
            "Address-state": safe(r.get("State")),
            "Address-country_id|disp": safe(r.get("Country")),
            "AltPhone": safe(r.get("Mobile No")),
            
        })

    return payloads
