import streamlit as st
import pandas as pd
import json
from google.oauth2.service_account import Credentials
import gspread
from datetime import datetime

# --- Load Google Sheets credentials ---
creds_dict = json.loads(st.secrets["google_service_account"])
creds = Credentials.from_service_account_info(creds_dict)
gc = gspread.authorize(creds)

# --- Constants ---
TOURNAMENT_LIST_SHEET = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/edit?usp=sharing"
RESULTS_SHEET = "https://docs.google.com/spreadsheets/d/1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs/edit?usp=sharing"

EVENTS = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

POINTS_MAPPING = {
    "A": {"1st":8, "2nd":5, "3rd":2},
    "B": {"1st":5, "2nd":3, "3rd":1},
    "AA":{"1st":15,"2nd":10,"3rd":5},
    "AAA":{"1st":20,"2nd":15,"3rd":10},
    "C": None  # For C tournaments, user enters points manually
}

# --- Load tournament list ---
tournaments_df = pd.read_csv(TOURNAMENT_LIST_SHEET)
tournaments_df['Tournament Name'] = tournaments_df['Tournament Name'].astype(str)

st.title("Tournament Score Tracker")

# --- User input ---
user_name = st.text_input("Enter your full name (First Last):").strip()
if not user_name:
    st.warning("Please enter your name to continue.")
    st.stop()

# Load or create user's tab
results_gsheet = gc.open_by_url(RESULTS_SHEET)
try:
    worksheet = results_gsheet.worksheet(user_name)
except gspread.WorksheetNotFound:
    worksheet = results_gsheet.add_worksheet(title=user_name, rows=100, cols=20)
    worksheet.append_row(["Date","Type","Tournament Name"] + EVENTS)

# Tournament selection
tournament_choice = st.selectbox("Select Tournament:", sorted(tournaments_df['Tournament Name'].unique()))
tournament_info = tournaments_df[tournaments_df['Tournament Name'] == tournament_choice].iloc[0]
tournament_date = tournament_info['Date']
tournament_type = tournament_info['Type']

st.markdown(f"**Date:** {tournament_date}  |  **Type:** {tournament_type}")

# --- Enter event results ---
st.subheader("Enter Results for Each Event")
results_input = {}
for event in EVENTS:
    if tournament_type == "C":
        results_input[event] = st.number_input(f"{event} points", min_value=0, step=1)
    else:
        results_input[event] = st.selectbox(f"{event} placement", ["", "1st","2nd","3rd"], index=0)

# --- Calculate total points ---
total_points = {}
for event, val in results_input.items():
    if tournament_type == "C":
        total_points[event] = val
    else:
        total_points[event] = POINTS_MAPPING[tournament_type].get(val, 0)

st.markdown("### Total Points per Event")
st.dataframe(pd.DataFrame([total_points]))

# --- Save to Google Sheet ---
if st.button("Save Results"):
    row = [tournament_date, tournament_type, tournament_choice] + [results_input[e] for e in EVENTS]
    worksheet.append_row(row)
    st.success("Results saved successfully!")
