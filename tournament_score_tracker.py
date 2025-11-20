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

    # Normalize types (both tournaments and competitor data)
    def norm_type(x):
        s = str(x).strip().lower()
        if "aaa" in s or s == "aaa": return "AAA"
        elif ("aa" in s and "aaa" not in s) or s == "aa": return "AA"
        elif "class a" in s or s == "a" or s == "class a": return "A"
        elif "class b" in s or s == "b" or s == "class b": return "B"
        elif "class c" in s or s == "c" or s == "class c": return "C"
        else: return None

    tournaments["TypeNorm"] = tournaments["Type"].apply(norm_type)
    # Use W-SUN so Fri/Sat are same weekend
    tournaments["Weekend"] = tournaments["Date"].dt.to_period("W-SUN")

    if "TypeNorm" not in df.columns:
        if "Type" in df.columns:
            df["TypeNorm"] = df["Type"].apply(norm_type)
        else:
            st.error("Missing 'Type' column in competitor sheets.")
            st.stop()

    today = pd.to_datetime(datetime.today().date())
    season_end = pd.to_datetime("2026-05-31")

    # Only tournaments within the season window
    future_tournaments = tournaments[(tournaments["Date"] > today) & (tournaments["Date"] <= season_end)].copy()
    future_tournaments["Weekend"] = future_tournaments["Date"].dt.to_period("W-SUN")

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

    def best5_sum(values):
        return sum(sorted(values, reverse=True)[:5])

    # Current A/B values by weekend:
    # - If any A on a weekend, that weekend is 8 (A dominates)
    # - Else use the best B value recorded for that weekend in the event column
    def ab_current_values(cdf_event, event_col):
        ab_df = cdf_event.loc[cdf_event["TypeNorm"].isin(["A", "B"]), ["Date", "TypeNorm", event_col]].copy()
        if ab_df.empty:
            return [], set()
        ab_df["Weekend"] = ab_df["Date"].dt.to_period("W-SUN")

        current_vals = []
        current_weekends = set()
        for wk, wk_df in ab_df.groupby("Weekend"):
            current_weekends.add(wk)
            if (wk_df["TypeNorm"] == "A").any():
                current_vals.append(8)
            else:
                b_vals = pd.to_numeric(wk_df.loc[wk_df["TypeNorm"] == "B", event_col], errors="coerce").fillna(0)
                current_vals.append(int(b_vals.max()) if not b_vals.empty else 0)
        return current_vals, current_weekends

    # Future A/B weekends within season window, excluding already-attended weekends.
    # If a future weekend has both A and B, count it as A (drop the B for that weekend).
    def ab_future_weekends(future_df, current_weekends):
        if future_df.empty:
            return set(), set()
        fut_a = set(future_df.loc[future_df["TypeNorm"] == "A", "Weekend"].unique().tolist()) - current_weekends
        fut_b_all = set(future_df.loc[future_df["TypeNorm"] == "B", "Weekend"].unique().tolist()) - current_weekends
        fut_b = fut_b_all - fut_a
        return fut_a, fut_b

    def calc_event(cdf_event, event_col):
        cdf_event[event_col] = pd.to_numeric(cdf_event[event_col], errors="coerce").fillna(0)

        # AAA current (cap 20)
        aaa_total = min(cdf_event.loc[cdf_event["TypeNorm"] == "AAA", event_col].sum(), 20)

        # AA current (best 2, cap 30)
        aa_series = cdf_event.loc[cdf_event["TypeNorm"] == "AA", event_col]
        aa_scores = aa_series.sort_values(ascending=False)
        current_aa_total = min(aa_scores.head(2).sum(), 30)
        current_aa_slots = (aa_series > 0).sum()

        # Remaining AA opportunities within season window (assume 15 per slot)
        future_aa = future_tournaments[future_tournaments["TypeNorm"] == "AA"]
        remaining_aa_opps = future_aa["Weekend"].nunique()
        aa_slots_left = max(0, 2 - current_aa_slots)
        additional_aa = min(aa_slots_left, remaining_aa_opps) * 15

        # A/B current using weekend dominance logic
        current_ab_values, current_ab_weekends = ab_current_values(cdf_event, event_col)
        current_ab_total = min(best5_sum(current_ab_values), 40)

        # A/B future weekends within season window, excluding already attended; A-first, B=5
        fut_a_wk, fut_b_wk = ab_future_weekends(future_tournaments, current_ab_weekends)
        future_ab_values = ([8] * len(fut_a_wk)) + ([5] * len(fut_b_wk))

        # Projected A/B = best 5 across current + future, cap 40
        projected_ab_total = min(best5_sum(current_ab_values + future_ab_values), 40)

        # C current (best 3, cap 9)
        c_scores = cdf_event.loc[cdf_event["TypeNorm"] == "C", event_col].sort_values(ascending=False)
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

    # Debug: show future A/B tournaments within season window and weekend counts
    with st.expander("🔍 Debug: Future A/B tournaments and weekend counts"):
        show_cols = [c for c in ["Date", "Type", "TypeNorm", "Tournament Name"] if c in future_tournaments.columns]
        st.dataframe(future_tournaments[show_cols], use_container_width=True)
        fut_a_weekends = future_tournaments.loc[future_tournaments["TypeNorm"] == "A", "Weekend"].nunique()
        fut_b_weekends = future_tournaments.loc[future_tournaments["TypeNorm"] == "B", "Weekend"].nunique()
        st.write("Remaining A weekends:", int(fut_a_weekends))
        st.write("Remaining B weekends (excluding weekends with A):", int(fut_b_weekends))

    st.caption(
        "ATA rules: AAA capped at 20; AA best 2 capped at 30; "
        "A/B combined best 5 weekends capped at 40 (A=8, B=5; Fri/Sat same weekend via W-SUN); "
        "C best 3 capped at 9. Season cutoff: tournaments after 2026-05-31 are excluded."
    )
