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

def reset_mode():
    st.session_state.mode = ""

if st.session_state.mode == "":
    st.session_state.mode = st.selectbox(
        "Choose an option:",
        ["", "Enter Tournament Scores", "View Results", "Edit Results"],
    )

# --- Get user name ---
user_name = st.text_input("Enter your name (First Last):").strip()
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
# FUNCTION: Update totals row with ATA limits
# ======================
def update_totals(ws, events):
    """Recalculate totals using ATA rules, remove old TOTALS, and sort by Date."""
    all_values = ws.get_all_records()
    df = pd.DataFrame(all_values)
    if df.empty:
        return

    # Remove any existing TOTALS rows
    df = df[df["Date"].astype(str).str.upper() != "TOTALS"]

    # Sort by Date (convert safely)
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date", ascending=True)
    df["Date"] = df["Date"].dt.strftime("%Y-%m-%d")

    # Convert numeric columns to numbers safely
    for col in events:
        df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    # Calculate total points per row
    df["TotalPoints"] = df[events].sum(axis=1)

    # ATA limits
    limits = {"Class AAA": 1, "Class AA": 2, "Class C": 3}
    ab_limit = 5  # Combined A + B

    selected_rows = pd.DataFrame()
    for t_type, limit in limits.items():
        subset = df[df["Type"] == t_type].sort_values("TotalPoints", ascending=False)
        selected_rows = pd.concat([selected_rows, subset.head(limit)])

    ab_subset = df[df["Type"].isin(["Class A", "Class B"])].sort_values("TotalPoints", ascending=False)
    selected_rows = pd.concat([selected_rows, ab_subset.head(ab_limit)])

    # Compute event totals from selected rows
    totals = {col: selected_rows[col].sum() for col in events}

    # Rewrite sheet — no old TOTALS line, always sorted
    ws.clear()
    ws.append_row(df.columns.drop("TotalPoints").tolist())
    ws.append_rows(df.drop(columns=["TotalPoints"]).astype(str).values.tolist())

    totals_row = ["TOTALS", "", "Counted Results"] + [str(round(totals.get(col, 0), 2)) for col in events]
    ws.append_row(totals_row)

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
        reset_mode()
        st.stop()

    st.subheader("Enter Your Results")

    results = {}
    if tourney_type == "Class C":
        for event in events:
            results[event] = st.number_input(f"{event} (Points)", min_value=0, step=1)
    else:
        places = ["", "1st", "2nd", "3rd"]
        for event in events:
            results[event] = st.selectbox(f"{event} (Place)", places, key=event)

    if st.button("💾 Save Results"):
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
        update_totals(worksheet, events)
        st.success("✅ Tournament results saved successfully!")

# ======================
# MODE 2: VIEW RESULTS
# ======================
elif st.session_state.mode == "View Results":
    if worksheet is None:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    data = worksheet.get_all_records()
    if not data:
        st.info("There are no Tournament Scores for this person.")
    else:
        df = pd.DataFrame(data)
        df = df[df["Date"] != "TOTALS"]

        st.markdown(
            """
            <style>
            [data-testid="stDataFrameResizable"] div {overflow: visible !important;}
            [data-testid="stHorizontalBlock"] {overflow-x: visible !important;}
            [data-testid="stVerticalBlock"] {overflow-y: visible !important;}
            div[data-testid="stDataFrameContainer"] {overflow: visible !important; width: 100% !important;}
            </style>
            """,
            unsafe_allow_html=True,
        )
        st.dataframe(df, use_container_width=True, hide_index=True)

# ======================
# MODE 3: EDIT RESULTS
# ======================
elif st.session_state.mode == "Edit Results":
    if worksheet is None:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    data = worksheet.get_all_records()
    if not data:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    df = pd.DataFrame(data)
    df = df[df["Date"] != "TOTALS"]

    st.markdown(
        """
        <style>
        [data-testid="stDataFrameResizable"] div {overflow: visible !important;}
        [data-testid="stHorizontalBlock"] {overflow-x: visible !important;}
        [data-testid="stVerticalBlock"] {overflow-y: visible !important;}
        div[data-testid="stDataFrameContainer"] {overflow: visible !important; width: 100% !important;}
        </style>
        """,
        unsafe_allow_html=True,
    )

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
