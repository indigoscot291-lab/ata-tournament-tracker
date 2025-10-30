import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# Load credentials from secrets
#creds_dict = st.secrets["google_service_account"]
#creds = Credentials.from_service_account_info(creds_dict)

# Connect to Google Sheets
#gc = gspread.authorize(creds)

st.set_page_config(page_title="Tournament Score Tracker", layout="wide")

# --- Load Google Sheets credentials from Streamlit secrets ---
creds_json = st.secrets["google_service_account"]
creds = Credentials.from_service_account_info(creds_json, scopes=[
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive"
])
gc = gspread.authorize(creds)

# --- Google Sheets IDs ---
TOURNAMENT_LIST_SHEET_ID = "16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE"
SCORES_SHEET_ID = "1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs"

# --- Load Tournament List ---
tournament_ws = gc.open_by_key(TOURNAMENT_LIST_SHEET_ID).sheet1
tournament_data = tournament_ws.get_all_records()
tournaments_df = pd.DataFrame(tournament_data)

# --- Input: User Name ---
st.title("Tournament Score Tracker")
user_name = st.text_input("Enter your First and Last Name:")

if not user_name.strip():
    st.warning("Please enter your name to continue.")
    st.stop()

# --- Input: Tournament ---
tournament_names = tournaments_df["Tournament Name"].unique()
selected_tournament = st.selectbox("Select Tournament:", tournament_names)

# Get tournament details
tourney_row = tournaments_df[tournaments_df["Tournament Name"] == selected_tournament].iloc[0]
tourney_date = tourney_row["Date"]
tourney_type = tourney_row["Type"]

st.write(f"**Date:** {tourney_date}  |  **Type:** {tourney_type}")

# --- Input: Event Results ---
events = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

# Points mapping by tournament type
POINTS_MAP = {
    "A": {"1st": 8, "2nd": 5, "3rd": 2},
    "B": {"1st": 5, "2nd": 3, "3rd": 1},
    "AA": {"1st": 15, "2nd": 10, "3rd": 5},
    "AAA": {"1st": 20, "2nd": 15, "3rd": 10},
    "C": None  # For C tournaments, user enters points directly
}

event_results = {}
for event in events:
    if tourney_type == "C":
        pts = st.number_input(f"{event} points (C Tournament)", min_value=0, step=1)
        event_results[event] = pts
    else:
        place = st.selectbox(f"{event} result:", ["", "1st", "2nd", "3rd"], key=event)
        event_results[event] = POINTS_MAP[tourney_type].get(place, 0)

# --- Calculate Total Points ---
total_points = sum(event_results.values())
st.write(f"**Total Points:** {total_points}")

# --- Save to Google Sheet ---
if st.button("Save Results"):
    # Open or create user tab
    try:
        score_ws = gc.open_by_key(SCORES_SHEET_ID).worksheet(user_name)
    except gspread.WorksheetNotFound:
        score_ws = gc.open_by_key(SCORES_SHEET_ID).add_worksheet(title=user_name, rows=100, cols=20)
        # Add headers
        score_ws.append_row(["Date", "Type", "Tournament Name"] + events)

    # Append new row
    new_row = [tourney_date, tourney_type, selected_tournament] + [event_results[e] for e in events]
    score_ws.append_row(new_row)
    st.success("✅ Results saved successfully!")

# --- Display User Sheet ---
st.subheader(f"{user_name}'s Tournament Scores")
score_ws = gc.open_by_key(SCORES_SHEET_ID).worksheet(user_name)
data = score_ws.get_all_records()
if data:
    df = pd.DataFrame(data)
    df["Total Points"] = df[events].sum(axis=1)
    st.dataframe(df, use_container_width=True)
else:
    st.info("No scores yet.")
