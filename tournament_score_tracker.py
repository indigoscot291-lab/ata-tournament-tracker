import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

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

# --- Maintain session state for main menu ---
if "mode" not in st.session_state:
    st.session_state.mode = ""

if st.session_state.mode == "":
    st.session_state.mode = st.selectbox(
        "Choose an option:",
        ["", "Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"],
    )
else:
    st.session_state.mode = st.selectbox(
        "Choose an option:",
        ["", "Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"],
        index=["", "Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"].index(st.session_state.mode),
    )

# --- Get list of existing worksheet names ---
try:
    existing_names = [ws.title for ws in client.open_by_key(SHEET_ID_MAIN).worksheets()]
except Exception:
    existing_names = []

# --- Get user name (different behavior by mode) ---
if st.session_state.mode == "Enter Tournament Scores":
    user_name_option = st.selectbox("Select existing competitor or add new:", [""] + existing_names + ["Add New Competitor"])
    if user_name_option == "Add New Competitor" or user_name_option == "":
        user_name = st.text_input("Enter new competitor name (First Last):").strip()
    else:
        user_name = user_name_option
elif st.session_state.mode in ["View Tournament Scores", "Edit Tournament Scores"]:
    user_name = st.selectbox("Select Competitor:", [""] + existing_names)
else:
    user_name = ""

if not user_name:
    st.stop()

# --- Helper: Get existing worksheet if it exists ---
def get_user_worksheet(name):
    try:
        return client.open_by_key(SHEET_ID_MAIN).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return None

worksheet = get_user_worksheet(user_name)

# ======================
# FUNCTION: Update totals row
# ======================
def update_totals(ws, events):
    all_values = ws.get_all_values()
    col_a = [row[0] for row in all_values if row]

    # Remove existing TOTALS and ATA TOTAL rows if any
    for label in ["TOTALS", "ATA TOTAL"]:
        if label in col_a:
            idx = col_a.index(label) + 1
            ws.delete_rows(idx)
            all_values.pop(idx - 1)

    # Insert TOTALS row at the end
    totals_row_idx = len(all_values) + 1
    ws.update_cell(totals_row_idx, 1, "TOTALS")

    start_col_idx = 4  # D = first event column
    for offset, _ in enumerate(events):
        col_idx = start_col_idx + offset
        col_letter = chr(64 + col_idx)
        formula = f"=SUM({col_letter}2:{col_letter}{totals_row_idx - 1})"
        ws.update_cell(totals_row_idx, col_idx, formula)

    # ======================
    # ATA TOTAL row
    # ======================
    df = pd.DataFrame(ws.get_all_records())
    df = df[df["Date"] != "TOTALS"]
    df["Total"] = df[events].sum(axis=1)

    # Apply ATA rules
    aaa = df[df["Type"] == "Class AAA"].sort_values("Total", ascending=False).head(1)
    aa = df[df["Type"] == "Class AA"].sort_values("Total", ascending=False).head(2)
    ab = df[df["Type"].isin(["Class A", "Class B"])].sort_values("Total", ascending=False).head(5)
    c = df[df["Type"] == "Class C"].sort_values("Total", ascending=False).head(3)

    ata_total = pd.concat([aaa, aa, ab, c])["Total"].sum()

    ata_row_idx = totals_row_idx + 1
    ws.update_cell(ata_row_idx, 1, "ATA TOTAL")
    ws.update_cell(ata_row_idx, 2, ata_total)

# ======================
# MODE 1: ENTER TOURNAMENT SCORES
# ======================
if st.session_state.mode == "Enter Tournament Scores":
    # Create worksheet if missing
    if worksheet is None:
        worksheet = client.open_by_key(SHEET_ID_MAIN).add_worksheet(
            title=user_name, rows=200, cols=20
        )
        headers = [
            "Date", "Type", "Tournament Name",
            "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
            "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
        ]
        worksheet.append_row(headers)
        st.info("🆕 New worksheet created for this competitor.")

    selected_tournament = st.selectbox("Select Tournament:", [""] + tournaments)
    if not selected_tournament:
        st.stop()

    # Lookup tournament info
    tourney_row = tournaments_df[tournaments_df["Tournament Name"] == selected_tournament].iloc[0]
    date = tourney_row["Date"]
    tourney_type = tourney_row["Type"]

    st.write(f"**Date:** {date}")
    st.write(f"**Type:** {tourney_type}")

    events = [
        "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
        "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
    ]

    # Check for duplicates
    sheet_df = pd.DataFrame(worksheet.get_all_records())
    if not sheet_df.empty and ((sheet_df["Date"] == date) & (sheet_df["Tournament Name"] == selected_tournament)).any():
        st.warning("⚠️ You have already entered results for this tournament.")
        st.stop()

    st.subheader("Enter Your Results")

    results = {}
