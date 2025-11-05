import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

# --- CONFIG ---
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
TOURNAMENT_LIST_SHEET = st.secrets["TOURNAMENT_LIST_SHEET"]

# Authenticate Google Sheets
creds = Credentials.from_service_account_info(
    st.secrets["gcp_service_account"], scopes=SCOPES
)
gc = gspread.authorize(creds)

# --- LOAD TOURNAMENTS ---
try:
    tournaments_df = pd.read_csv(TOURNAMENT_LIST_SHEET)
except Exception:
    tournaments_df = pd.DataFrame(
        columns=["Date", "Type", "Tournament Name"]
    )

# --- EVENT COLUMNS ---
EVENTS = [
    "Traditional Forms", "Traditional Weapons",
    "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons",
    "xTreme Forms", "xTreme Weapons"
]


# ------------------ FUNCTION: UPDATE TOTALS ------------------
def update_totals(ws, events):
    all_data = ws.get_all_records()
    if not all_data:
        return

    df = pd.DataFrame(all_data)

    # Remove totals rows (old totals)
    df = df[df["Date"] != "TOTALS"]

    # Convert to datetime safely
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

    # Handle weird manual entries — fill invalids with 1900-01-01 for sorting
    df["Date"] = df["Date"].fillna(pd.Timestamp("1900-01-01"))

    df = df.sort_values("Date").reset_index(drop=True)

    # Ensure Counted ✅ column exists
    if "Counted ✅" not in df.columns:
        df["Counted ✅"] = ""

    # Remove existing TOTALS row if still in sheet
    all_values = ws.get_all_values()
    col_a = [row[0] for row in all_values if row]
    if "TOTALS" in col_a:
        totals_row_idx = col_a.index("TOTALS") + 1
        ws.delete_rows(totals_row_idx)

    # Determine which rows count based on type limits
    counted_flags = []
    type_limits = {"Class AAA": 1, "Class AA": 2, "Class A": 5, "Class B": 5, "Class C": 3}
    used = {t: 0 for t in type_limits.keys()}

    for _, row in df.iterrows():
        t_type = row["Type"]
        if used.get(t_type, 0) < type_limits.get(t_type, 0):
            counted_flags.append(True)
            used[t_type] += 1
        else:
            counted_flags.append(False)

    df["Counted ✅"] = ["✅" if c else "" for c in counted_flags]

    # Build totals row
    totals = ["TOTALS", "", ""]
    for event in events:
        totals.append(df.loc[df["Counted ✅"] == "✅", event].sum())
    totals.append("")  # final Counted ✅ col

    # Convert everything to strings for JSON safety
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df = df.fillna("")
    df = df.astype(str)

    # Write all back to Google Sheet
    ws.clear()
    ws.append_row(df.columns.tolist())
    ws.append_rows(df.values.tolist())
    ws.append_row([str(x) for x in totals])


# ------------------ FUNCTION: ENTER SCORES ------------------
def enter_scores():
    st.header("Enter Tournament Scores")

    name = st.text_input("Competitor Name").strip()
    if not name:
        st.info("Enter your name to continue.")
        return

    # Check or create worksheet
    try:
        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        if st.session_state.get("selected_option") == "Enter Tournament Scores":
            worksheet = gc.open_by_key(SPREADSHEET_ID).add_worksheet(title=name, rows="100", cols="20")
            worksheet.append_row(["Date", "Type", "Tournament Name"] + EVENTS + ["Counted ✅"])
        else:
            st.warning("There are no Tournament Scores for this person.")
            return

    # Tournament selection
    t_choice = st.selectbox("Select Tournament:", [""] + tournaments_df["Tournament Name"].tolist())

    if t_choice:
        selected_row = tournaments_df[tournaments_df["Tournament Name"] == t_choice].iloc[0]
        t_date = selected_row["Date"]
        t_type = selected_row["Type"]

        existing = worksheet.get_all_records()
        if any((row["Date"] == t_date and row["Tournament Name"] == t_choice) for row in existing):
            st.warning("You have already entered results for this tournament.")
            return

        st.write(f"**Date:** {t_date} | **Type:** {t_type}")
        scores = {}
        for event in EVENTS:
            scores[event] = st.number_input(f"{event}", min_value=0, max_value=10, step=1)

        if st.button("Submit Results"):
            new_row = [t_date, t_type, t_choice] + [scores[e] for e in EVENTS] + [""]
            worksheet.append_row(new_row)
            update_totals(worksheet, EVENTS)
            st.success("Tournament results added successfully!")


# ------------------ FUNCTION: VIEW RESULTS ------------------
def view_results():
    st.header("View Tournament Results")

    name = st.text_input("Competitor Name").strip()
    if not name:
        st.info("Enter a name to view results.")
        return

    try:
        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        st.warning("There are no Tournament Scores for this person.")
        return

    data = worksheet.get_all_values()
    if not data or len(data) < 2:
        st.info("No tournament results available.")
        return

    df = pd.DataFrame(data[1:], columns=data[0])
    st.dataframe(
        df.style.hide(axis="index"),
        use_container_width=True,
        height=len(df) * 35 + 50
    )


# ------------------ FUNCTION: EDIT RESULTS ------------------
def edit_results():
    st.header("Edit Tournament Results")

    name = st.text_input("Competitor Name").strip()
    if not name:
        st.info("Enter a name to view results.")
        return

    try:
        worksheet = gc.open_by_key(SPREADSHEET_ID).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        st.warning("There are no Tournament Scores for this person.")
        return

    data = worksheet.get_all_values()
    if not data or len(data) < 2:
        st.info("No data to edit.")
        return

    df = pd.DataFrame(data[1:], columns=data[0])
    df = df[df["Date"] != "TOTALS"]

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True)
    if st.button("Save Changes"):
        worksheet.clear()
        worksheet.append_row(df.columns.tolist())
        worksheet.append_rows(edited_df.values.tolist())
        update_totals(worksheet, EVENTS)
        st.success("Changes saved and totals recalculated.")


# ------------------ MAIN APP ------------------
st.title("ATA Tournament Score Tracker")

options = ["Enter Tournament Scores", "View Results", "Edit Results"]
choice = st.selectbox("Choose an option:", options, key="selected_option")

if choice == "Enter Tournament Scores":
    enter_scores()
elif choice == "View Results":
    view_results()
elif choice == "Edit Results":
    edit_results()
