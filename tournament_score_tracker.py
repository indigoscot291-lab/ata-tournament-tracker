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
# Main menu
mode = st.selectbox(
    "Choose an option:",
    [
        "Enter Tournament Scores",
        "View Tournament Scores",
        "Edit Tournament Scores",
        "View Tournament Results",
        "Maximum Points Projection (All Events)"
    ]
)

# Existing competitors
try:
    existing_names = [ws.title for ws in client.open_by_key(SHEET_ID_MAIN).worksheets()]
except Exception:
    existing_names = []

# Global competitor selection ONLY for these modes
user_name = ""
if mode == "Enter Tournament Scores":
    user_name_option = st.selectbox(
        "Select existing competitor or add new:",
        [""] + existing_names + ["Add New Competitor"]
    )
    if user_name_option in ["", "Add New Competitor"]:
        user_name = st.text_input("Enter new competitor name (First Last):").strip()
    else:
        user_name = user_name_option

elif mode in ["View Tournament Scores", "Edit Tournament Scores"]:
    user_name = st.selectbox("Select Competitor:", [""] + existing_names)

# Stop ONLY for modes that rely on the global name
if mode in ["Enter Tournament Scores", "View Tournament Scores", "Edit Tournament Scores"] and not user_name:
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
    from datetime import datetime

    st.subheader("🥋 View Tournament Results")

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

    # Assign placements per event (allowing duplicates)
    for event in event_cols:
        scores = df[["Name", event]].copy()
        scores[event] = pd.to_numeric(scores[event], errors="coerce").fillna(0)

        placed = {}
        for _, row in scores.iterrows():
            score = row[event]
            name = row["Name"]
            if score == POINTS_MAP[tourney_type]["1st"]:
                placed[name] = "1st"
            elif score == POINTS_MAP[tourney_type]["2nd"]:
                placed[name] = "2nd"
            elif score == POINTS_MAP[tourney_type]["3rd"]:
                placed[name] = "3rd"
            else:
                placed[name] = "DNP"

        for name in placement_table.index:
            placement_table.at[name, event] = placed.get(name, "DNP")

    # Display results
    st.subheader(f"🏆 Event Placements for {selected_tourney}")
    st.dataframe(placement_table.style.set_properties(**{'text-align': 'left'}), use_container_width=True)
# ======================
# MODE 6: MAXIMUM POINTS PROJECTION (ALL EVENTS)
# ======================
elif mode == "Maximum Points Projection (All Events)":
    st.subheader("📈 Maximum Points Projection (All Events)")

    # --- Load both competitor sheets ---
    comp_urls = [
        "https://docs.google.com/spreadsheets/d/1W7q6YjLYMqY9bdv5G77KdK2zxUKET3NZMQb9Inu2F8w/export?format=csv",  # 50–59 1st degree women
        "https://docs.google.com/spreadsheets/d/1tCWIc-Zeog8GFH6fZJJR-85GHbC1Kjhx50UvGluZqdg/export?format=csv"   # 40–49 2nd/3rd degree women
    ]

    comp_frames = []
    for url in comp_urls:
        df_part = pd.read_csv(url)
        df_part.columns = df_part.columns.str.strip()
        df_part["Date"] = pd.to_datetime(df_part["Date"], errors="coerce")
        comp_frames.append(df_part)

    df = pd.concat(comp_frames, ignore_index=True)

    # --- Load tournament metadata sheet ---
    tourney_url = "https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv"
    tournaments = pd.read_csv(tourney_url)
    tournaments.columns = tournaments.columns.str.strip()
    tournaments["Date"] = pd.to_datetime(tournaments["Date"], errors="coerce")

    # Normalize tournament types
    def norm_type(x):
        s = str(x).strip().lower()
        if "aaa" in s: return "AAA"
        if "aa" in s: return "AA"
        if "class a" in s or s == "a": return "A"
        if "class b" in s or s == "b": return "B"
        if "class c" in s or s == "c": return "C"
        return None

    tournaments["TypeNorm"] = tournaments["Type"].apply(norm_type)
    tournaments["Weekend"] = tournaments["Date"].dt.to_period("W")

    today = pd.to_datetime(datetime.today().date())
    future_tournaments = tournaments[tournaments["Date"] > today]
    future_aa = future_tournaments[future_tournaments["TypeNorm"] == "AA"]
    future_ab = future_tournaments[future_tournaments["TypeNorm"].isin(["A", "B"])]

    # --- Choose competitor across both sheets ---
    competitor = st.selectbox("Choose competitor:", sorted(df["Name"].dropna().unique()))
    if not competitor:
        st.stop()

    cdf = df[df["Name"].str.strip().eq(competitor)].copy()
    if cdf.empty:
        st.info("No scores available for this competitor yet.")
        st.stop()

    # --- Event columns ---
    event_cols = [
        "Forms", "Weapons", "Combat Weapons", "Sparring",
        "Creative Forms", "Creative Weapons", "X-Treme Forms", "X-Treme Weapons"
    ]

    def calc_event(cdf, event_col):
        cdf[event_col] = pd.to_numeric(cdf[event_col], errors="coerce").fillna(0)

        # AAA current
        aaa_total = min(cdf.loc[cdf["Type"]=="AAA", event_col].sum(), 20)

        # AA current
        aa_scores = cdf.loc[cdf["Type"]=="AA", event_col].sort_values(ascending=False)
        current_aa_total = min(aa_scores.head(2).sum(), 30)
        current_aa_slots = (cdf.loc[cdf["Type"]=="AA", event_col] > 0).sum()

        # Remaining AA opportunities
        remaining_aa_opps = future_aa.shape[0]
        aa_slots_left = max(0, 2 - current_aa_slots)
        additional_aa = min(aa_slots_left, remaining_aa_opps) * 15

        # A/B current
        ab_df = cdf.loc[cdf["Type"].isin(["A","B"]), ["Date", event_col]].copy()
        if not ab_df.empty:
            ab_df["Weekend"] = ab_df["Date"].dt.to_period("W")
            best_per_weekend = ab_df.groupby("Weekend")[event_col].max()
            current_ab_total = min(best_per_weekend.sort_values(ascending=False).head(5).sum(), 40)
            current_weekends = best_per_weekend.shape[0]
        else:
            current_ab_total, current_weekends = 0, 0

        # Remaining A/B weekends
        rem_weekends = future_ab["Date"].dt.to_period("W").nunique()

        # Projected A/B = best 5 weekends across past+future, with future weekends assumed 8
        existing_scores = list(best_per_weekend.values) if current_weekends > 0 else []
        future_scores = [8] * rem_weekends
        combined = sorted(existing_scores + future_scores, reverse=True)
        projected_ab_total = min(sum(combined[:5]), 40)

        # C current
        c_scores = cdf.loc[cdf["Type"]=="C", event_col].sort_values(ascending=False)
        current_c_total = min(c_scores.head(3).sum(), 9)

        current_total = aaa_total + current_aa_total + current_ab_total + current_c_total
        projected_max = aaa_total + current_aa_total + additional_aa + projected_ab_total

        return current_total, projected_max

    projection = []
    for event in event_cols:
        if event not in cdf.columns:
            st.warning(f"Column '{event}' not found in sheet")
            continue
        cur, proj = calc_event(cdf.copy(), event)
        projection.append({"Event": event, "Current Points": cur, "Projected Max": proj})

    proj_df = pd.DataFrame(projection)
    st.dataframe(proj_df, use_container_width=True, hide_index=True)

    st.caption("ATA rules applied: AAA capped at 20, AA best 2 capped at 30 (only remaining AA tournaments count), A/B best 5 weekends capped at 40 (future weekends assumed 8), C best 3 capped at 9. Projection adjusts dynamically as tournaments happen. Competitors are now selectable across both 50–59 and 40–49 sheets.")
