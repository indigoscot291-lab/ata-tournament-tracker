import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# ======================
# GOOGLE SHEETS SETUP
# ======================
SHEET_ID_MAIN = "1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs"
TOURNAMENT_LIST_SHEET = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv"

# Load credentials
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

# --- Open or create worksheet ---
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
selected_tournament = st.selectbox("Select Tournament:", [""] + tournaments, key="tournament_select")
if not selected_tournament:
    st.stop()

# Lookup tournament info
tourney_row = tournaments_df[tournaments_df["Tournament Name"] == selected_tournament].iloc[0]
date = tourney_row["Date"]
tourney_type = tourney_row["Type"]
st.write(f"**Date:** {date}")
st.write(f"**Type:** {tourney_type}")

# ======================
# CHECK FOR EXISTING ENTRY
# ======================
all_values = worksheet.get_all_values()
headers = all_values[0] if all_values else []
rows = all_values[1:]
existing_entry = None
existing_row_index = None

for i, row in enumerate(rows, start=2):  # Start at row 2 (after header)
    if len(row) >= 3 and row[0] == date and row[2] == selected_tournament:
        existing_entry = dict(zip(headers, row))
        existing_row_index = i
        break

# --- Edit / Cancel Logic ---
if existing_entry and "TOTALS" not in existing_entry["Date"]:
    st.warning("⚠️ You have already entered results for this tournament.")
    col1, col2 = st.columns(2)
    if col1.button("✏️ Edit existing entry"):
        st.session_state["edit_mode"] = True
        st.session_state["existing_entry"] = existing_entry
        st.session_state["existing_row_index"] = existing_row_index
    if col2.button("❌ Cancel"):
        # Fully clear state and rerun cleanly
        for key in list(st.session_state.keys()):
            del st.session_state[key]
        st.experimental_set_query_params()  # clear UI
        st.rerun()

edit_mode = st.session_state.get("edit_mode", False)
existing_entry = st.session_state.get("existing_entry", None)

# ======================
# EVENT INPUT
# ======================
events = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]
st.subheader("Enter Your Results")

results = {}
POINTS_MAP = {
    "Class A": {"1st": 8, "2nd": 5, "3rd": 2},
    "Class B": {"1st": 5, "2nd": 3, "3rd": 1},
    "Class AA": {"1st": 15, "2nd": 10, "3rd": 8},
    "Class AAA": {"1st": 20, "2nd": 15, "3rd": 10},
}
reverse_points = {v: k for c in POINTS_MAP.values() for k, v in c.items()}

if tourney_type == "Class C":
    for event in events:
        default_val = 0
        if edit_mode and existing_entry and existing_entry.get(event, "").isdigit():
            default_val = int(existing_entry[event])
        results[event] = st.number_input(f"{event} (Points)", min_value=0, step=1, value=default_val)
else:
    places = ["", "1st", "2nd", "3rd"]
    for event in events:
        default_place = ""
        if edit_mode and existing_entry:
            val = existing_entry.get(event, "")
            if val.isdigit() and int(val) in reverse_points:
                default_place = reverse_points[int(val)]
        results[event] = st.selectbox(
            f"{event} (Place)",
            places,
            index=places.index(default_place) if default_place in places else 0,
            key=event,
        )

# ======================
# SAVE
# ======================
if st.button("💾 Save Results"):
    new_row = [date, tourney_type, selected_tournament]
    for event in events:
        if tourney_type == "Class C":
            new_row.append(results[event])
        else:
            new_row.append(POINTS_MAP.get(tourney_type, {}).get(results[event], 0))

    # --- Remove old entry if editing ---
    if edit_mode and st.session_state.get("existing_row_index"):
        worksheet.delete_rows(st.session_state["existing_row_index"])
        st.info("📝 Existing entry replaced.")

    # --- Insert in proper date order ---
    col_a = worksheet.col_values(1)
    if "TOTALS" in col_a:
        totals_row_idx = col_a.index("TOTALS") + 1
    else:
        totals_row_idx = len(col_a) + 1

    insert_row_idx = totals_row_idx
    try:
        new_date_obj = datetime.strptime(str(date), "%m/%d/%Y")
        for i, row in enumerate(rows, start=2):
            if len(row) > 0 and row[0] not in ("TOTALS", ""):
                try:
                    existing_date = datetime.strptime(str(row[0]), "%m/%d/%Y")
                    if new_date_obj < existing_date:
                        insert_row_idx = i
                        break
                except:
                    continue
    except:
        pass

    worksheet.insert_row(new_row, insert_row_idx)

    # --- Ensure totals row exists ---
    col_a = worksheet.col_values(1)
    if "TOTALS" not in col_a:
        worksheet.append_row(["TOTALS"] + [""] * (len(events) + 2))
        totals_row_idx = len(worksheet.get_all_values())

    # --- Recalculate totals ---
    all_values = worksheet.get_all_values()
    totals_row_idx = [i + 1 for i, r in enumerate(all_values) if r and r[0] == "TOTALS"][0]
    start_col_idx = 4
    for offset, _ in enumerate(events):
        col_idx = start_col_idx + offset
        col_letter = chr(64 + col_idx)
        formula = f"=SUM({col_letter}2:{col_letter}{totals_row_idx - 1})"
        worksheet.update_cell(totals_row_idx, col_idx, formula)

    # --- Reset state and rerun ---
    for key in list(st.session_state.keys()):
        del st.session_state[key]
    st.success(f"✅ Results for '{selected_tournament}' on {date} saved successfully!")
    st.rerun()
