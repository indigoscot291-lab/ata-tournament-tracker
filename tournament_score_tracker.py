import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

st.set_page_config(page_title="ATA Tournament Tracker", layout="wide")

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=SCOPES)
gc = gspread.authorize(creds)

# Spreadsheet info
SPREADSHEET_ID = "YOUR_SPREADSHEET_ID"  # Replace this
worksheet = gc.open_by_key(SPREADSHEET_ID).sheet1

# Load data
data = worksheet.get_all_records()
df = pd.DataFrame(data)

if df.empty:
    st.warning("Your Google Sheet is empty. Please make sure it has headers.")
    st.stop()

# --- UI ---
st.header("🏆 ATA Tournament Results Entry")

# Tournament selection and date input
tournament_name = st.selectbox("Select Tournament Name:", sorted(df["Tournament Name"].unique()))
tournament_date = st.date_input("Tournament Date:")

# Check if existing entry
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

# Event columns
event_cols = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

# --- Input section ---
st.subheader("Enter Results")
results = {}
for event in event_cols:
    default_val = entry_data.get(event, "") if edit_mode else ""
    results[event] = st.text_input(event, default_val)

if st.button("💾 Save Results"):
    # Create or update row data
    new_row = {
        "Date": str(tournament_date),
        "Type": existing_entry["Type"].iloc[0] if edit_mode else "Class A",  # default or existing
        "Tournament Name": tournament_name,
    }
    new_row.update(results)

    # Remove totals if exists
    totals_index = df[df["Date"] == "Totals"].index
    if not totals_index.empty:
        worksheet.delete_rows(totals_index[0] + 2)  # +2 because of header row

    # Re-fetch current data
    all_data = worksheet.get_all_records()
    df = pd.DataFrame(all_data)

    # Remove old entry if editing
    if edit_mode:
        df = df[~((df["Tournament Name"] == tournament_name) & (df["Date"] == str(tournament_date)))]

    # Add new/updated row
    df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

    # Sort by date
    try:
        df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
        df = df.sort_values("Date").reset_index(drop=True)
        df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    except Exception as e:
        st.error(f"Error sorting by date: {e}")

    # Write back to Google Sheet
    worksheet.clear()
    worksheet.append_row(df.columns.tolist())
    worksheet.append_rows(df.values.tolist())

    # Add totals row at bottom
    total_row = ["Totals", "", ""]
    num_rows = len(df) + 1  # header included
    for col_num in range(4, 4 + len(event_cols)):
        col_letter = chr(64 + col_num)
        total_row.append(f"=SUM({col_letter}2:{col_letter}{num_rows})")
    worksheet.append_row(total_row)

    st.success("✅ Results saved and list sorted by date!")
    st.rerun()
