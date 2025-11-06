import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# --- SETUP ---
st.set_page_config(page_title="ATA Tournament Score Tracker", layout="wide")

# --- GOOGLE SHEETS CONNECTION ---
try:
    SERVICE_ACCOUNT = st.secrets["gcp_service_account"]
    SPREADSHEET_ID = st.secrets["SPREADSHEET_ID"]
except Exception:
    st.error("Missing Streamlit secrets. Please configure credentials in Streamlit Cloud.")
    st.stop()

SCOPE = ["https://www.googleapis.com/auth/spreadsheets"]
creds = Credentials.from_service_account_info(SERVICE_ACCOUNT, scopes=SCOPE)
client = gspread.authorize(creds)
spreadsheet = client.open_by_key(SPREADSHEET_ID)

# --- LOAD TOURNAMENT LIST ---
TOURNAMENT_LIST_SHEET = "TournamentList"
try:
    tournaments_df = pd.read_csv(TOURNAMENT_LIST_SHEET)
except Exception:
    tournaments_df = pd.DataFrame(columns=["Date", "Location", "Class"])

# --- PAGE SETUP ---
st.title("ATA Tournament Score Tracker")

option = st.selectbox(
    "Select Option:",
    ["View Tournament Results", "Enter Tournament Scores", "Edit Tournament Scores"]
)

# --- LOAD EXISTING SHEETS ---
sheets = {ws.title: pd.DataFrame(ws.get_all_records()) for ws in spreadsheet.worksheets()}
existing_names = list(sheets.keys())

# --- VIEW TOURNAMENT SCORES ---
if option == "View Tournament Results":
    st.title("View Tournament Scores")

    name = st.selectbox("Select Competitor:", existing_names)
    if name:
        if name in sheets:
            df = sheets[name].sort_values("Date", ascending=True)

            # Calculate totals row
            numeric_cols = df.select_dtypes(include='number').columns
            totals_row = df[numeric_cols].sum().to_frame().T
            totals_row.insert(0, 'Date', 'TOTALS')
            for col in df.columns:
                if col not in totals_row.columns:
                    totals_row[col] = ""

            # Append totals row
            df = pd.concat([df, totals_row], ignore_index=True)

            st.dataframe(df, use_container_width=True, hide_index=True)
        else:
            st.warning("There are no Tournament Scores for this person.")

# --- ENTER TOURNAMENT SCORES ---
elif option == "Enter Tournament Scores":
    st.title("Enter Tournament Scores")

    name = st.text_input("Enter Competitor Name:")
    existing_name_option = st.selectbox("Or select existing competitor (optional):", [""] + existing_names)

    if existing_name_option:
        name = existing_name_option

    if name:
        tournament = st.text_input("Tournament Name:")
        date = st.date_input("Date:")
        division = st.text_input("Division:")
        class_type = st.selectbox("Class:", ["AAA", "AA", "A", "B", "C"])
        score = st.number_input("Score:", min_value=0.0, step=0.1)

        if st.button("Save Score"):
            try:
                if name not in existing_names:
                    worksheet = spreadsheet.add_worksheet(title=name, rows="100", cols="20")
                    df = pd.DataFrame(columns=["Date", "Tournament", "Division", "Class", "Score"])
                else:
                    worksheet = spreadsheet.worksheet(name)
                    df = pd.DataFrame(worksheet.get_all_records())

                new_row = {"Date": str(date), "Tournament": tournament, "Division": division, "Class": class_type, "Score": score}
                df = pd.concat([df, pd.DataFrame([new_row])], ignore_index=True)

                worksheet.update([df.columns.values.tolist()] + df.values.tolist())
                st.success(f"Score added for {name}")
            except Exception as e:
                st.error(f"Error saving score: {e}")

# --- EDIT TOURNAMENT SCORES ---
elif option == "Edit Tournament Scores":
    st.title("Edit Tournament Scores")

    name = st.selectbox("Select Competitor:", existing_names)
    if name:
        if name in sheets:
            df = sheets[name].sort_values("Date", ascending=True)
            st.dataframe(df, use_container_width=True, hide_index=True)  # hide_index added here
        else:
            st.warning("There are no Tournament Scores for this person.")
