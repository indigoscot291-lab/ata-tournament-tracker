import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- Constants ---
SHEET_URL = "https://docs.google.com/spreadsheets/d/1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs/edit?usp=sharing"
TOURNAMENT_LIST_SHEET = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv"

POINTS_MAP = {
    "A": {"1st": 8, "2nd": 5, "3rd": 2},
    "B": {"1st": 5, "2nd": 3, "3rd": 1},
    "AA": {"1st": 15, "2nd": 10, "3rd": 5},
    "AAA": {"1st": 20, "2nd": 15, "3rd": 10},
    "C": {}  # handled separately
}

TOURNEY_TYPE_MAP = {
    "Class A": "A",
    "Class B": "B",
    "Class C": "C",
    "Class AA": "AA",
    "Class AAA": "AAA"
}

EVENTS = ["Traditional Forms","Traditional Weapons","Combat Sparring",
          "Traditional Sparring","Creative Forms","Creative Weapons",
          "xTreme Forms","xTreme Weapons"]

# --- Google Sheets Auth ---
creds_json = st.secrets["google_service_account"]
creds = Credentials.from_service_account_info(creds_json, scopes=["https://www.googleapis.com/auth/spreadsheets"])
gc = gspread.authorize(creds)
sheet = gc.open_by_url(SHEET_URL)

# --- App UI ---
st.title("ATA Tournament Score Tracker")

# User name input
user_name = st.text_input("Enter Competitor Name (First Last):").strip()
if not user_name:
    st.warning("Please enter your name to continue.")
    st.stop()

# Load tournaments
tournaments_df = pd.read_csv(TOURNAMENT_LIST_SHEET)
tournament_names = tournaments_df["Tournament Name"].tolist()

tourney_choice = st.selectbox("Select Tournament:", tournament_names)

tourney_info = tournaments_df[tournaments_df["Tournament Name"] == tourney_choice].iloc[0]
date = tourney_info["Date"]
tourney_type = tourney_info["Type"]

st.write(f"**Date:** {date}")
st.write(f"**Tournament Type:** {tourney_type}")

# Normalize type for points
tourney_type_clean = TOURNEY_TYPE_MAP.get(tourney_type.strip(), None)
if not tourney_type_clean:
    st.warning(f"Unrecognized tournament type: {tourney_type}. Using 0 points for all events.")

# Event results input
event_results = {}
for event in EVENTS:
    if tourney_type_clean == "C":
        pts = st.number_input(f"{event} points (C Tournament)", min_value=0, step=1, key=event)
        event_results[event] = pts
    else:
        place = st.selectbox(f"{event} result:", ["", "1st", "2nd", "3rd"], key=event)
        event_results[event] = POINTS_MAP.get(tourney_type_clean, {}).get(place, 0)

# Display totals
st.subheader("Total Points")
total_points = sum(event_results.values())
st.write(f"**Total Points:** {total_points}")
points_df = pd.DataFrame([event_results])
st.dataframe(points_df.T.rename(columns={0:"Points"}))

# Save to Google Sheet
if st.button("Save Results"):
    try:
        try:
            comp_sheet = sheet.worksheet(user_name)
        except gspread.WorksheetNotFound:
            comp_sheet = sheet.add_worksheet(title=user_name, rows="100", cols="20")

        # Check if headers exist
        headers = comp_sheet.row_values(1)
        if not headers:
            comp_sheet.append_row(["Date","Type","Tournament Name"] + EVENTS)

        row_values = [date, tourney_type, tourney_choice] + [event_results[e] for e in EVENTS]
        comp_sheet.append_row(row_values)
        st.success("Results saved successfully!")
    except Exception as e:
        st.error(f"Failed to save results: {e}")
