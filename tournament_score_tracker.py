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

if st.session_state.mode == "":
    st.session_state.mode = st.selectbox(
        "Choose an option:",
        ["", "Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"],
    )
else:
    st.session_state.mode = st.selectbox(
        "Choose an option:",
        ["", "Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"],
        index=["", "Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"].index(st.session_state.mode),
    )

# --- Get list of existing worksheet names ---
try:
    existing_names = [ws.title for ws in client.open_by_key(SHEET_ID_MAIN).worksheets()]
except Exception:
    existing_names = []

# --- Get user name (different behavior by mode) ---
if st.session_state.mode == "Enter Tournament Scores":
    user_name_option = st.selectbox("Select existing competitor or add new:", [""] + existing_names + ["Add New Competitor"])
    if user_name_option == "Add New Competitor" or user_name_option == "":
        user_name = st.text_input("Enter new competitor name (First Last):").strip()
    else:
        user_name = user_name_option
elif st.session_state.mode in ["View Tournament Scores", "Edit Tournament Scores"]:
    user_name = st.selectbox("Select Competitor:", [""] + existing_names)
else:
    user_name = ""

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
# FUNCTION: Update totals row (ATA TOTAL only)
# ======================
def update_totals(ws, events):
    all_values = ws.get_all_values()
    col_a = [row[0] for row in all_values if row]

    # Remove existing ATA TOTAL row if any
    if "ATA TOTAL" in col_a:
        ata_row_idx = col_a.index("ATA TOTAL") + 1
        ws.delete_rows(ata_row_idx)
        all_values.pop(ata_row_idx - 1)

    # Prepare DataFrame
    df = pd.DataFrame(ws.get_all_records())
    df = df[df["Date"] != "ATA TOTAL"]
    df["Total"] = df[events].sum(axis=1)

    # Apply ATA rules
    aaa = df[df["Type"] == "Class AAA"].sort_values("Total", ascending=False).head(1)
    aa = df[df["Type"] == "Class AA"].sort_values("Total", ascending=False).head(2)
    ab = df[df["Type"].isin(["Class A", "Class B"])].sort_values("Total", ascending=False).head(5)
    c = df[df["Type"] == "Class C"].sort_values("Total", ascending=False).head(3)

    ata_total = pd.concat([aaa, aa, ab, c])["Total"].sum()

    # Insert ATA TOTAL row at the end
    ata_row_idx = len(all_values) + 1
    ws.update_cell(ata_row_idx, 1, "ATA TOTAL")
    ws.update_cell(ata_row_idx, 2, ata_total)

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

        # Resort by date
        df = pd.DataFrame(worksheet.get_all_records())
        if "Date" in df.columns:
            df = df.sort_values("Date").reset_index(drop=True)
            worksheet.clear()
            worksheet.append_row(df.columns.tolist())
            worksheet.append_rows(df.values.tolist())

        update_totals(worksheet, events)
        st.success("✅ Tournament results saved successfully!")

# ======================
# MODE 2: VIEW RESULTS
# ======================
elif st.session_state.mode == "View Tournament Scores":
    if worksheet is None:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    data = worksheet.get_all_records()
    if not data:
        st.info("There are no Tournament Scores for this person.")
    else:
        df = pd.DataFrame(data)

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
elif st.session_state.mode == "Edit Tournament Scores":
    if worksheet is None:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    data = worksheet.get_all_records()
    if not data:
        st.info("There are no Tournament Scores for this person.")
        st.stop()

    df = pd.DataFrame(data)
    df = df[df["Date"] != "ATA TOTAL"]

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

        st.success("✅ Changes saved successfully and ATA total updated!")
