import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- CONFIG ---
MAIN_SHEET_URL = "https://docs.google.com/spreadsheets/d/1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs/edit?usp=sharing"
TOURNAMENT_LIST_SHEET = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/edit?usp=sharing"

# --- GOOGLE AUTH ---
scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
creds = Credentials.from_service_account_info(st.secrets["google_service_account"], scopes=scope)
gc = gspread.authorize(creds)

# --- LOAD SHEETS ---
main_sheet = gc.open_by_url(MAIN_SHEET_URL)
tournament_df = pd.read_csv(TOURNAMENT_LIST_SHEET.replace("/edit?usp=sharing", "/export?format=csv"))

# --- APP UI ---
st.title("🏆 ATA Tournament Score Tracker")

name = st.text_input("Enter your full name (First Last):")
if name:
    # Get or create user's sheet
    try:
        worksheet = main_sheet.worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        worksheet = main_sheet.add_worksheet(title=name, rows="100", cols="20")
        headers = [
            "Date", "Type", "Tournament Name",
            "Traditional Forms", "Traditional Weapons",
            "Combat Sparring", "Traditional Sparring",
            "Creative Forms", "Creative Weapons",
            "xTreme Forms", "xTreme Weapons"
        ]
        worksheet.append_row(headers)

    selected_tournament = st.selectbox("Select Tournament:", sorted(tournament_df["Tournament Name"].dropna().unique()))

    if selected_tournament:
        row = tournament_df[tournament_df["Tournament Name"] == selected_tournament].iloc[0]
        date = row["Date"]
        tourney_type = row["Type"]

        st.write(f"**Tournament Date:** {date}")
        st.write(f"**Type:** {tourney_type}")

        st.markdown("---")

        st.subheader("Enter Your Results")
        events = [
            "Traditional Forms", "Traditional Weapons",
            "Combat Sparring", "Traditional Sparring",
            "Creative Forms", "Creative Weapons",
            "xTreme Forms", "xTreme Weapons"
        ]

        results = {}
        for event in events:
            if tourney_type == "Class C":
                # C tournaments: user enters custom points
                points = st.number_input(f"{event} Points:", min_value=0, max_value=100, step=1)
                results[event] = points
            else:
                results[event] = st.selectbox(
                    f"{event} Placement:",
                    ["", "1st", "2nd", "3rd"],
                    key=event
                )

        if st.button("💾 Save Results"):
            # Points system
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

            worksheet.append_row(new_row)

            # --- ADD SUM FORMULAS ---
            all_values = worksheet.get_all_values()
            last_row = len(all_values) + 1  # Next available row

            # Add SUM formulas for each event
            for col_idx, _ in enumerate(events, start=4):  # D -> K
                formula = f"=SUM({chr(64 + col_idx)}2:{chr(64 + col_idx)}{last_row - 1})"
                worksheet.update_cell(last_row, col_idx, formula)

            st.success("✅ Tournament results saved successfully!")

