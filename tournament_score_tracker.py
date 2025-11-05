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

if "mode" not in st.session_state:
    st.session_state.mode = ""

def reset_mode():
    st.session_state.mode = ""

if st.session_state.mode == "":
    st.session_state.mode = st.selectbox(
        "Choose an option:",
        ["", "Enter Tournament Scores", "View Results", "Edit Results"],
    )

user_name = st.text_input("Enter your name (First Last):").strip()
if not user_name:
    st.stop()

def get_user_worksheet(name):
    try:
        return client.open_by_key(SHEET_ID_MAIN).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return None

worksheet = get_user_worksheet(user_name)

# ======================
# FUNCTION: UPDATE TOTALS
# ======================
def update_totals(ws, events):
    data = ws.get_all_records()
    if not data:
        return

    df = pd.DataFrame(data)
    df = df[df["Date"] != "TOTALS"]

    # Convert dates safely
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date", ascending=True).reset_index(drop=True)

    # Determine which scores count
    type_limits = {"Class AAA": 1, "Class AA": 2, "Class A": 5, "Class B": 5, "Class C": 3}
    df["Counted ✅"] = ""

    used = {k: 0 for k in type_limits}
    for i, row in df.iterrows():
        t_type = row.get("Type", "")
        if t_type in type_limits and used[t_type] < type_limits[t_type]:
            df.at[i, "Counted ✅"] = "✅"
            used[t_type] += 1

    # Remove existing TOTALS line from sheet if present
    all_values = ws.get_all_values()
    col_a = [r[0] for r in all_values if r]
    if "TOTALS" in col_a:
        idx = col_a.index("TOTALS") + 1
        ws.delete_rows(idx)

    # Create totals row based only on ✅ rows
    totals = ["TOTALS", "", ""]
    for e in events:
        totals.append(df.loc[df["Counted ✅"] == "✅", e].sum())
    totals.append("")

    # Convert to string to avoid JSON errors
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")
    df = df.fillna("").astype(str)

    # Rewrite sheet cleanly
    ws.clear()
    ws.append_row(df.columns.tolist())
    ws.append_rows(df.values.tolist())
    ws.append_row(totals)


# ======================
# ENTER TOURNAMENT SCORES
# ======================
if st.session_state.mode == "Enter Tournament Scores":
    if worksheet is None:
        worksheet = client.open_by_key(SHEET_ID_MAIN).add_worksheet(
            title=user_name, rows=200, cols=20
        )
        headers = [
            "Date", "Type", "Tournament Name",
            "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
            "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons",
            "Counted ✅"
        ]
        worksheet.append_row(headers)
        st.info("🆕 New worksheet created for this competitor.")

    selected_tournament = st.selectbox("Select Tournament:", [""] + tournaments)
    if not selected_tournament:
        st.stop()

    tourney_row = tournaments_df[tournaments_df["Tournament Name"] == selected_tournament].iloc[0]
    date = tourney_row["Date"]
    tourney_type = tourney_row["Type"]

    st.write(f"**Date:** {date}")
    st.write(f"**Type:** {tourney_type}")

    events = [
        "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
        "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
    ]

    sheet_df = pd.DataFrame(worksheet.get_all_records())
    if not sheet_df.empty and ((sheet_df["Date"] == date) & (sheet_df["Tournament Name"] == selected_tournament)).any():
        st.warning("⚠️ You have already entered results for this tournament.")
        st.stop()

    st.subheader("Enter Your Results")

    results = {}
    for e in events:
        results[e] = st.number_input(f"{e} (Points)", min_value=0, step=1)

    if st.button("💾 Save Results"):
        new_row = [date, tourney_type, selected_tournament] + [results[e] for e in events] + [""]
        worksheet.append_row(new_row)
        update_totals(worksheet, events)
        st.success("✅ Tournament results saved and totals updated!")


# ======================
# VIEW RESULTS
# ======================
elif st.session_state.mode == "View Results":
    if worksheet is None:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    data = worksheet.get_all_values()
    if not data or len(data) < 2:
        st.info("No results found.")
        st.stop()

    df = pd.DataFrame(data[1:], columns=data[0])
    st.dataframe(df, use_container_width=True, hide_index=True)


# ======================
# EDIT RESULTS
# ======================
elif st.session_state.mode == "Edit Results":
    if worksheet is None:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    data = worksheet.get_all_values()
    if not data or len(data) < 2:
        st.info("No tournament results available.")
        st.stop()

    df = pd.DataFrame(data[1:], columns=data[0])
    df = df[df["Date"] != "TOTALS"]

    edited_df = st.data_editor(df, num_rows="dynamic", use_container_width=True, hide_index=True)

    if st.button("💾 Save Changes"):
        worksheet.clear()
        worksheet.append_row(df.columns.tolist())
        worksheet.append_rows(edited_df.values.tolist())
        update_totals(worksheet, [
            "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
            "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
        ])
        st.success("✅ Changes saved successfully and totals updated!")
