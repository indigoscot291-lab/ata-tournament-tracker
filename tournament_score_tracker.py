import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="ATA Tournament Tracker", layout="wide")

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
gc = gspread.authorize(creds)

# Replace with your sheet ID and worksheet name
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"
WORKSHEET_NAME = "Sheet1"

worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(WORKSHEET_NAME)

# Load data
data = worksheet.get_all_records()
df = pd.DataFrame(data)

if df.empty:
    st.warning("Your Google Sheet is empty. Please make sure it has headers.")
    st.stop()

# Tournament selection
st.header("🏆 ATA Tournament Results Entry")

tournament_name = st.selectbox("Select Tournament Name:", sorted(df["Tournament Name"].unique()))
tournament_date = st.date_input("Tournament Date:")

# Check for existing entry
existing_entry = df[(df["Tournament Name"] == tournament_name) & (df["Date"] == str(tournament_date))]

edit_mode = False
entry_data = {}

if not existing_entry.empty:
    st.warning("⚠️ You’ve already entered results for this tournament.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("✏️ Edit Existing Entry"):
            edit_mode = True
            entry_data = existing_entry.iloc[0].to_dict()
    with col2:
        if st.button("❌ Cancel"):
            st.rerun()

# Event categories
event_cols = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

st.subheader("Enter Results")

results = {}
for event in event_cols:
    default_val = entry_data.get(event, "") if edit_mode else ""
    results[event] = st.text_input(event, default_val)

if st.button("💾 Save Results"):
    new_row = {
        "Date": str(tournament_date),
        "Type": existing_entry["Type"].iloc[0] if edit_mode else "Class A",  # Default or existing
        "Tournament Name": tournament_name,
    }
    new_row.update(results)

    # Remove old totals row if exists
    totals_index = df[df["Date"] == "Totals"].index
    if not totals_index.empty:
        worksheet.delete_rows(totals_index[0] + 2)  # +2 because Google Sheets is 1-indexed

    # Overwrite if editing
    if edit_mode:
        row_index = existing_entry.index[0] + 2  # header row + 1
        worksheet.delete_rows(row_index)
        worksheet.insert_row(list(new_row.values()), row_index)
        st.success("✅ Entry updated successfully!")
    else:
        worksheet.append_row(list(new_row.values()))
        st.success("✅ New entry added successfully!")

    # Add totals row at bottom
    total_row = ["Totals", "", ""]
    num_rows = len(worksheet.get_all_values())
    for col_num in range(4, 4 + len(event_cols)):
        col_letter = chr(64 + col_num)
        total_row.append(f"=SUM({col_letter}2:{col_letter}{num_rows})")
    worksheet.append_row(total_row)

    st.rerun()
