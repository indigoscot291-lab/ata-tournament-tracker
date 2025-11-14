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

# --- Main menu dropdown ---
mode = st.selectbox(
    "Choose an option:",
    ["Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores", "View Tournament Results"]
)
st.write(f"Selected mode: '{mode}'")

# --- Get list of existing worksheet names ---
try:
    existing_names = [ws.title for ws in client.open_by_key(SHEET_ID_MAIN).worksheets()]
except Exception:
    existing_names = []

# --- Get user name (different behavior by mode) ---
if mode == "Enter Tournament Scores":
    user_name_option = st.selectbox("Select existing competitor or add new:", [""] + existing_names + ["Add New Competitor"])
    if user_name_option == "Add New Competitor" or user_name_option == "":
        user_name = st.text_input("Enter new competitor name (First Last):").strip()
    else:
        user_name = user_name_option
elif mode in ["View Tournament Scores", "Edit Tournament Scores"]:
    user_name = st.selectbox("Select Competitor:", [""] + existing_names)
else:
    user_name = ""

if mode != "View Tournament Results" and not user_name:
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
    # Get all values and remove existing "Totals" row
    all_values = ws.get_all_values()
    col_a = [row[0] for row in all_values if row]

    if "Totals" in col_a:
        idx = col_a.index("Totals") + 1
        ws.delete_rows(idx)

    # Load and clean data
    df = pd.DataFrame(ws.get_all_records())
    df = df[~df["Date"].isin(["Totals"])]
    df["Date"] = pd.to_datetime(df["Date"], errors="coerce")
    df = df[df["Date"].notna()]
    df = df.sort_values("Date").reset_index(drop=True)

    # Ensure all event columns are numeric
    for event in events:
        df[event] = pd.to_numeric(df[event], errors="coerce").fillna(0)

    # Calculate per-event totals using ATA rules
    totals_by_event = []
    for event in events:
        aaa_score = df[df["Type"] == "Class AAA"][event].nlargest(1).sum()
        aa_score = df[df["Type"] == "Class AA"][event].nlargest(2).sum()
        ab_score = df[df["Type"].isin(["Class A", "Class B"])][event].nlargest(5).sum()
        c_score = df[df["Type"] == "Class C"][event].nlargest(3).sum()
        total = aaa_score + aa_score + ab_score + c_score
        totals_by_event.append(float(total))  # Ensure native float for JSON serialization

    # Rebuild sheet
    df["Date"] = df["Date"].dt.strftime("%m/%d/%Y")
    rows = df.fillna("").astype(str).values.tolist()

    ws.clear()
    ws.append_row(df.columns.tolist())
    ws.append_rows(rows)

    # Insert Totals row aligned under event columns (starts at column D)
    ws.append_row(["Totals", "", ""] + totals_by_event)


# ======================
# MODE 1: ENTER TOURNAMENT SCORES
# ======================
if mode == "Enter Tournament Scores":
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
            "Class AA": {"1st": 15, "2nd": 10, "3rd": 8},
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

    # ✅ Reset mode to return to main menu
    #st.session_state.mode = ""
    #st.session_state.saved = False


# ======================
# MODE 2: VIEW RESULTS
# ======================
elif mode == "View Tournament Scores":
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
elif mode == "Edit Tournament Scores":
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

# ================================
# MODE 4: VIEW TOURNAMENT RESULTS
# ================================
elif mode == "View Tournament Results":
    st.write("✅ View Tournament Results block is active")

    try:
        from datetime import datetime

        # Load tournament metadata
        tourney_url = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv&gid=327661053"
        tournaments_df = pd.read_csv(tourney_url)
        tournaments_df["Date"] = pd.to_datetime(tournaments_df["Date"], errors="coerce")
        today = pd.to_datetime(datetime.today().date())

        # Filter: completed tournaments, not Class C
        completed = tournaments_df[
            (tournaments_df["Date"] <= today) &
            (tournaments_df["Type"] != "Class C")
        ]

        # Choose division
        sheet_map = {
            "50–59 1st Degree Black Belt": "1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg",
            "40–49 2nd/3rd Degree Black Belt": "1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w"
        }
        division = st.selectbox("Choose division:", list(sheet_map.keys()))
        result_url = f"https://docs.google.com/spreadsheets/d/{sheet_map[division]}/export?format=csv&gid=0"
        results_df = pd.read_csv(result_url)

        # Filter tournaments that actually have results
        valid_tourneys = completed[
            completed["Tournament Name"].isin(results_df["Tournament"].unique())
        ]["Tournament Name"].dropna().sort_values().unique()

        selected_tourney = st.selectbox("Select a completed tournament:", [""] + list(valid_tourneys))
        if not selected_tourney:
            st.stop()

        # Get tournament type
        tourney_type = completed[completed["Tournament Name"] == selected_tourney]["Type"].iloc[0]

        # Filter results for selected tournament
        df = results_df[results_df["Tournament"] == selected_tourney]

        # Define event columns
        event_cols = [
            "Forms", "Weapons", "Combat Weapons", "Sparring",
            "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
        ]

        # Clean scores
        for col in event_cols:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

        # Scoring map
        POINTS_MAP = {
            "Class AAA": {"1st": 20, "2nd": 15, "3rd": 10},
            "Class AA": {"1st": 15, "2nd": 10, "3rd": 8},
            "Class A": {"1st": 8, "2nd": 5, "3rd": 2},
            "Class B": {"1st": 5, "2nd": 3, "3rd": 1}
        }

        # Initialize placement table
        placement_table = pd.DataFrame(index=df["Name"].unique(), columns=event_cols)

        # Assign placements per event
        for event in event_cols:
            scores = df[["Name", event]].copy()
            scores = scores.sort_values(event, ascending=False)

            placed = {}
            for _, row in scores.iterrows():
                score = row[event]
                name = row["Name"]
                if score == POINTS_MAP[tourney_type]["1st"] and "1st" not in placed.values():
                    placed[name] = "1st"
                elif score == POINTS_MAP[tourney_type]["2nd"] and "2nd" not in placed.values():
                    placed[name] = "2nd"
                elif score == POINTS_MAP[tourney_type]["3rd"] and "3rd" not in placed.values():
                    placed[name] = "3rd"

            for name in placement_table.index:
                placement_table.at[name, event] = placed.get(name, "DNP")

        # Display results
        st.subheader(f"🏆 Event Placements for {selected_tourney}")
        st.dataframe(placement_table.style.set_properties(**{'text-align': 'left'}), use_container_width=True)
else:
    st.error("⚠️ No matching mode block was triggered.")
st.write("✅ End of script reached")    
    
