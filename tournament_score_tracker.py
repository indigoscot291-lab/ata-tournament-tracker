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
creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
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

# Make or open user's sheet tab
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
        results[event] = st.number_input(f"{event} (Points)", min_value=0, step=1)
else:
    places = ["", "1st", "2nd", "3rd"]
    for event in events:
        results[event] = st.selectbox(f"{event} (Place)", places, key=event)

# ======================
# SAVE TO SHEET
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

    # --- Find totals row (look for "TOTALS" in column A) ---
    col_a = worksheet.col_values(1)
    if "TOTALS" in col_a:
        totals_row_idx = col_a.index("TOTALS") + 1
        insert_row_idx = totals_row_idx  # insert directly above totals
    else:
        insert_row_idx = len(col_a) + 1  # append at bottom if no totals yet

    # --- Insert new result row ---
    worksheet.insert_row(new_row, insert_row_idx)

    # --- If totals row doesn't exist, create it ---
    if "TOTALS" not in col_a:
        totals_row_idx = insert_row_idx + 1
        worksheet.update_cell(totals_row_idx, 1, "TOTALS")

    # --- Recalculate SUM formulas ---
    all_values = worksheet.get_all_values()
    totals_row_idx = [i + 1 for i, row in enumerate(all_values) if row and row[0] == "TOTALS"][0]

    start_col_idx = 4  # D = first event column
    for offset, _ in enumerate(events):
        col_idx = start_col_idx + offset
        col_letter = chr(64 + col_idx)
        formula = f"=SUM({col_letter}2:{col_letter}{totals_row_idx - 1})"
        worksheet.update_cell(totals_row_idx, col_idx, formula)

    st.success("✅ Tournament results saved successfully, totals updated!")
