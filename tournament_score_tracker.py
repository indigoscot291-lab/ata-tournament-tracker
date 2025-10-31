import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ======================
# GOOGLE SHEETS SETUP
# ======================
SHEET_ID_MAIN = "1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs"
TOURNAMENT_LIST_SHEET = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv"

# Load credentials from Streamlit secrets
creds_json = st.secrets["google_service_account"]
creds = Credentials.from_service_account_info(
    creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"]
)
client = gspread.authorize(creds)

# ======================
# LOAD TOURNAMENT LIST
# ======================
try:
    tournaments_df = pd.read_csv(TOURNAMENT_LIST_SHEET)
    tournaments_df = tournaments_df.dropna(subset=["Tournament Name"])
    tournaments_df["Tournament Name"] = tournaments_df["Tournament Name"].astype(str)
    tournaments = tournaments_df["Tournament Name"].unique().tolist()
    st.success("✅ Tournament list loaded")
except Exception as e:
    st.error(f"Failed to load tournament list: {e}")
    st.stop()

# ======================
# STREAMLIT UI
# ======================
st.title("🏆 ATA Tournament Score Tracker")

# --- User input ---
user_name = st.text_input("Enter your name (First Last):").strip()
if not user_name:
    st.stop()

# --- Make or open user's sheet tab ---
try:
    try:
        worksheet = client.open_by_key(SHEET_ID_MAIN).worksheet(user_name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = client.open_by_key(SHEET_ID_MAIN).add_worksheet(title=user_name, rows=100, cols=20)
        headers = [
            "Date", "Type", "Tournament Name",
            "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
            "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
        ]
        worksheet.append_row(headers)
        st.info("🆕 New worksheet created for this competitor.")
except Exception as e:
    st.error(f"Error accessing user sheet: {e}")
    st.stop()

# --- Tournament selection ---
selected_tournament = st.selectbox("Select Tournament:", [""] + tournaments)
if not selected_tournament:
    st.stop()

# Lookup tournament info
tourney_row = tournaments_df[tournaments_df["Tournament Name"] == selected_tournament].iloc[0]
date = tourney_row["Date"]
tourney_type = tourney_row["Type"]

st.write(f"**Date:** {date}")
st.write(f"**Type:** {tourney_type}")

# ======================
# DUPLICATE CHECK
# ======================
existing_records = worksheet.get_all_records()
existing_df = pd.DataFrame(existing_records)

existing_entry = None
if not existing_df.empty:
    mask = (existing_df["Date"] == date) & (existing_df["Tournament Name"] == selected_tournament)
    if mask.any():
        existing_entry = existing_df.loc[mask].iloc[0]

edit_mode = False
if existing_entry is not None:
    st.warning("⚠️ You have already entered results for this tournament.")
    col1, col2 = st.columns(2)
    if col1.button("✏️ Edit existing entry"):
        edit_mode = True
    elif col2.button("❌ Cancel"):
        st.stop()

# ======================
# EVENT RESULTS INPUT
# ======================
events = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

st.subheader("Enter Your Results")

results = {}
if tourney_type == "Class C":
    for event in events:
        prefill = int(existing_entry[event]) if edit_mode and pd.notna(existing_entry[event]) else 0
        results[event] = st.number_input(f"{event} (Points)", min_value=0, step=1, value=prefill)
else:
    places = ["", "1st", "2nd", "3rd"]
    for event in events:
        prefill_val = ""
        if edit_mode and pd.notna(existing_entry[event]):
            val = int(existing_entry[event])
            if val == 8 or val == 15 or val == 20:
                prefill_val = "1st"
            elif val == 5 or val == 10 or val == 15:
                prefill_val = "2nd"
            elif val == 2 or val == 5 or val == 10:
                prefill_val = "3rd"
        results[event] = st.selectbox(f"{event} (Place)", places, index=places.index(prefill_val) if prefill_val in places else 0, key=event)

# ======================
# SAVE / EDIT RESULTS
# ======================
if st.button("💾 Save Results"):
    POINTS_MAP = {
        "Class A": {"1st": 8, "2nd": 5, "3rd": 2},
        "Class B": {"1st": 5, "2nd": 3, "3rd": 1},
        "Class AA": {"1st": 15, "2nd": 10, "3rd": 5},
        "Class AAA": {"1st": 20, "2nd": 15, "3rd": 10},
    }

    new_row = [date, tourney_type, selected_tournament]
    for event in events:
        if tourney_type == "Class C":
            new_row.append(results[event])
        else:
            new_row.append(POINTS_MAP.get(tourney_type, {}).get(results[event], 0))

    # --- Handle edit mode ---
    if edit_mode:
        # Find and replace the existing entry
        for i, row in enumerate(existing_records):
            if row["Date"] == date and row["Tournament Name"] == selected_tournament:
                worksheet.delete_rows(i + 2)  # +2 because of header row
                break
        st.info("📝 Updated existing tournament entry.")

    # --- Insert row in date order ---
    all_data = worksheet.get_all_values()
    dates = [r[0] for r in all_data[1:] if r and r[0] != "TOTALS"]
    insert_row_idx = len(all_data) + 1

    try:
        from datetime import datetime
        new_date_obj = datetime.strptime(str(date), "%m/%d/%Y")
        for i, d in enumerate(dates):
            try:
                existing_date = datetime.strptime(str(d), "%m/%d/%Y")
                if new_date_obj < existing_date:
                    insert_row_idx = i + 2  # +2 for header row
                    break
            except:
                continue
    except Exception:
        pass

    # --- Find totals row ---
    col_a = worksheet.col_values(1)
    if "TOTALS" in col_a:
        totals_row_idx = col_a.index("TOTALS") + 1
        if insert_row_idx >= totals_row_idx:
            insert_row_idx = totals_row_idx

    worksheet.insert_row(new_row, insert_row_idx)

    # --- Add totals row if missing ---
    if "TOTALS" not in col_a:
        totals_row_idx = insert_row_idx + 1
        worksheet.update_cell(totals_row_idx, 1, "TOTALS")

    # --- Recalculate totals formulas ---
    all_values = worksheet.get_all_values()
    totals_row_idx = [i + 1 for i, row in enumerate(all_values) if row and row[0] == "TOTALS"][0]
    start_col_idx = 4
    for offset, _ in enumerate(events):
        col_idx = start_col_idx + offset
        col_letter = chr(64 + col_idx)
        formula = f"=SUM({col_letter}2:{col_letter}{totals_row_idx - 1})"
        worksheet.update_cell(totals_row_idx, col_idx, formula)

    st.success("✅ Tournament results saved successfully and totals updated!")
