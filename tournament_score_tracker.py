  import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

st.set_page_config(page_title="ATA Tournament Score Tracker", layout="wide")

# -----------------------------
# GOOGLE AUTHENTICATION
# -----------------------------
creds_json = st.secrets["google_service_account"]
creds = Credentials.from_service_account_info(creds_json)
gc = gspread.authorize(creds)

# URLs for sheets
SCORES_SHEET_URL = "https://docs.google.com/spreadsheets/d/1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs/edit?usp=sharing"
TOURNAMENTS_SHEET_URL = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/edit?usp=sharing"

# Open sheets
scores_doc = gc.open_by_url(SCORES_SHEET_URL)
tournament_doc = gc.open_by_url(TOURNAMENTS_SHEET_URL)

# Load tournament names
try:
    tournament_df = pd.DataFrame(tournament_doc.sheet1.get_all_records())
    tournaments = sorted(tournament_df["Tournament Name"].dropna().unique())
except Exception as e:
    st.error(f"Failed to load tournament list: {e}")
    st.stop()

# -----------------------------
# POINTS CONFIGURATION
# -----------------------------
POINTS = {
    "A": { "1st": 8, "2nd": 5, "3rd": 2 },
    "B": { "1st": 5, "2nd": 3, "3rd": 1 },
    "AA": { "1st": 15, "2nd": 10, "3rd": 5 },
    "AAA": { "1st": 20, "2nd": 15, "3rd": 10 }
}

EVENTS = [
    "Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
    "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

# -----------------------------
# APP LOGIC
# -----------------------------
st.title("🏆 ATA Tournament Score Tracker")

# User entry
first_name = st.text_input("First Name")
last_name = st.text_input("Last Name")

if not first_name or not last_name:
    st.info("Please enter both your **First** and **Last Name** to begin.")
    st.stop()

tab_name = f"{first_name.strip().title()} {last_name.strip().title()}"

# Create or open user’s sheet tab
try:
    try:
        user_sheet = scores_doc.worksheet(tab_name)
    except gspread.exceptions.WorksheetNotFound:
        user_sheet = scores_doc.add_worksheet(title=tab_name, rows=200, cols=20)
        # Add headers
        headers = ["Date", "Type", "Tournament Name"] + EVENTS
        user_sheet.append_row(headers)
except Exception as e:
    st.error(f"Error accessing your sheet tab: {e}")
    st.stop()

# Tournament selection
selected_tournament = st.selectbox("Select Tournament", [""] + tournaments)

if selected_tournament:
    t_row = tournament_df[tournament_df["Tournament Name"] == selected_tournament].iloc[0]
    date = t_row["Date"]
    t_type = t_row["Type"]

    st.markdown(f"**Date:** {date}  \n**Type:** {t_type}")

    st.divider()
    st.markdown("### 🥋 Enter Your Results")

    entries = {}
    for event in EVENTS:
        if t_type.strip().upper() == "C":
            # Allow numeric entry for C tournaments
            entries[event] = st.number_input(f"{event} (Enter Points)", min_value=0, step=1, key=event)
        else:
            entries[event] = st.selectbox(f"{event}", ["", "1st", "2nd", "3rd"], key=event)

    st.divider()

    # Submit
    if st.button("Submit Results"):
        try:
            new_row = [date, t_type, selected_tournament]
            for event in EVENTS:
                val = entries[event]
                if t_type.strip().upper() != "C":
                    points = POINTS.get(t_type.strip().upper(), {}).get(val, 0)
                else:
                    points = val
                new_row.append(points)

            user_sheet.append_row(new_row)
            st.success(f"✅ Results saved for {selected_tournament}!")
        except Exception as e:
            st.error(f"Error saving results: {e}")

# -----------------------------
# DISPLAY EXISTING DATA
# -----------------------------
st.divider()
st.subheader("📊 Your Tournament Summary")

try:
    data = pd.DataFrame(user_sheet.get_all_records())
    if not data.empty:
        # Compute totals
        totals = data[EVENTS].sum().to_dict()
        totals_df = pd.DataFrame([totals])

        st.dataframe(data, use_container_width=True, hide_index=True)
        st.markdown("### 🧮 Total Points by Event")
        st.dataframe(totals_df, use_container_width=True, hide_index=True)
    else:
        st.info("No scores recorded yet.")
except Exception as e:
    st.error(f"Error loading your scores: {e}")
