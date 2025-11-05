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

if "mode" not in st.session_state:
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

# --- Helper: Get worksheet ---
def get_user_worksheet(name):
    try:
        return client.open_by_key(SHEET_ID_MAIN).worksheet(name)
    except gspread.exceptions.WorksheetNotFound:
        return None

worksheet = get_user_worksheet(user_name)

# ======================
# FUNCTION: Update totals and count logic
# ======================
def update_totals(ws, events):
    all_data = ws.get_all_records()
    df = pd.DataFrame(all_data)
    if df.empty:
        return

    df = df[df["Date"] != "TOTALS"]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df.sort_values("Date").reset_index(drop=True)

    # Remove any existing TOTALS row from worksheet
    all_values = ws.get_all_values()
    col_a = [row[0] for row in all_values if row]
    if "TOTALS" in col_a:
        totals_row_idx = col_a.index("TOTALS") + 1
        ws.delete_rows(totals_row_idx)

    # Identify which rows count toward totals
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

    # Calculate totals only for counted tournaments
    totals = ["TOTALS", "", ""]
    for event in events:
        totals.append(df.loc[df["Counted ✅"] == "✅", event].sum())

    df = df.sort_values("Date").reset_index(drop=True)
    ws.clear()
    ws.append_row(df.columns.tolist())
    ws.append_rows(df.values.tolist())
    ws.append_row(totals)

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
            "Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons", "Counted ✅"
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

        # Resort + update totals
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
        df = df.sort_values("Date").reset_index(drop=True)

        # Remove scrollbars and show full width
        st.markdown(
            """
            <style>
            [data-testid="stDataFrameResizable"] div {
                overflow: visible !important;
            }
            [data-testid="stHorizontalBlock"] {overflow-x: visible !important;}
            [data-testid="stVerticalBlock"] {overflow-y: visible !important;}
            div[data-testid="stDataFrameContainer"] {
                overflow: visible !important;
                width: 100% !important;
            }
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
    df = df.sort_values("Date").reset_index(drop=True)

    st.markdown(
        """
        <style>
        [data-testid="stDataFrameResizable"] div {
            overflow: visible !important;
        }
        [data-testid="stHorizontalBlock"] {overflow-x: visible !important;}
        [data-testid="stVerticalBlock"] {overflow-y: visible !important;}
        div[data-testid="stDataFrameContainer"] {
            overflow: visible !important;
            width: 100% !important;
        }
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
