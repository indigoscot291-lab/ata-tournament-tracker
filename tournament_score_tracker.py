import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials

# ======================

# GOOGLE SHEETS SETUP

# ======================

SHEET_ID_MAIN = "1GsxPhcrKvQ-eUOov4F8XiPONOS6fhF648Xb8-m6JiCs"
TOURNAMENT_LIST_SHEET = "[https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv](https://docs.google.com/spreadsheets/d/16ORyU9066rDdQCeUTjWYlIVtEYLdncs5EG89IoANOeE/export?format=csv)"

# Load credentials from Streamlit secrets

creds_json = st.secrets["google_service_account"]
creds = Credentials.from_service_account_info(
creds_json,
scopes=["[https://www.googleapis.com/auth/spreadsheets](https://www.googleapis.com/auth/spreadsheets)"]
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

# --- Mode selection ---

mode = st.selectbox(
"Select an option:",
["Enter Tournament Scores", "View Results", "Edit Results"]
)

# --- User input ---

user_name = st.text_input("Enter your name (First Last):").strip()
if not user_name:
st.stop()

# --- Make or open user's sheet tab (only when entering scores) ---

if mode == "Enter Tournament Scores":
try:
try:
worksheet = client.open_by_key(SHEET_ID_MAIN).worksheet(user_name)
except gspread.exceptions.WorksheetNotFound:
worksheet = client.open_by_key(SHEET_ID_MAIN).add_worksheet(title=user_name, rows=100, cols=20)
headers = [
"Date", "Type", "Tournament Name",
"Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
"Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]
worksheet.append_row(headers)
st.info("🆕 New worksheet created for this competitor.")
except Exception as e:
st.error(f"Error accessing user sheet: {e}")
st.stop()

# ======================

# FUNCTIONS

# ======================

def load_user_data(name):
try:
ws = client.open_by_key(SHEET_ID_MAIN).worksheet(name)
data = pd.DataFrame(ws.get_all_values())
data.columns = data.iloc[0]
data = data[1:]
return data, ws
except gspread.exceptions.WorksheetNotFound:
return None, None

def update_totals(ws, events):
all_values = ws.get_all_values()
if not all_values:
return
col_headers = all_values[0]
totals_row_idx = None
for i, row in enumerate(all_values):
if row and row[0] == "TOTALS":
totals_row_idx = i + 1
break
if not totals_row_idx:
totals_row_idx = len(all_values) + 1
ws.update_cell(totals_row_idx, 1, "TOTALS")
for idx, event in enumerate(events):
col_idx = col_headers.index(event) + 1
formula = f"=SUM({chr(64+col_idx)}2:{chr(64+col_idx)}{totals_row_idx-1})"
ws.update_cell(totals_row_idx, col_idx, formula)

POINTS_MAP = {
"Class A": {"1st": 8, "2nd": 5, "3rd": 2},
"Class B": {"1st": 5, "2nd": 3, "3rd": 1},
"Class AA": {"1st": 15, "2nd": 10, "3rd": 5},
"Class AAA": {"1st": 20, "2nd": 15, "3rd": 10},
}

events = [
"Traditional Forms", "Traditional Weapons", "Combat Sparring", "Traditional Sparring",
"Creative Forms", "Creative Weapons", "xTreme Forms", "xTreme Weapons"
]

# ======================

# ENTER TOURNAMENT SCORES

# ======================

if mode == "Enter Tournament Scores":
selected_tournament = st.selectbox("Select Tournament:", [""] + tournaments)
if not selected_tournament:
st.stop()

```
tourney_row = tournaments_df[tournaments_df["Tournament Name"] == selected_tournament].iloc[0]
date = tourney_row["Date"]
tourney_type = tourney_row["Type"]

# Check if tournament already entered
user_data, worksheet = load_user_data(user_name)
if user_data is not None:
    already_entered = ((user_data["Date"] == date) & (user_data["Tournament Name"] == selected_tournament)).any()
    if already_entered:
        st.warning("You have already entered results for this tournament.")
        st.stop()

st.write(f"**Date:** {date}")
st.write(f"**Type:** {tourney_type}")

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
    new_row = [date, tourney_type, selected_tournament]
    for event in events:
        if tourney_type == "Class C":
            new_row.append(results[event])
        else:
            new_row.append(POINTS_MAP.get(tourney_type, {}).get(results[event], 0))

    # Insert row in date order
    all_rows = worksheet.get_all_values()
    if len(all_rows) <= 1:
        insert_idx = 2
    else:
        insert_idx = 2
        for i, row in enumerate(all_rows[1:], start=2):
            if row[0] > date:
                insert_idx = i
                break
        else:
            insert_idx = len(all_rows) + 1
    worksheet.insert_row(new_row, insert_idx)
    update_totals(worksheet, events)
    st.success("✅ Tournament results saved successfully, totals updated!")
```

# ======================

# VIEW RESULTS

# ======================

elif mode == "View Results":
user_data, _ = load_user_data(user_name)
if user_data is None:
st.info("There are no Tournament Scores for this person.")
st.stop()
st.subheader(f"{user_name}'s Tournament Results")
st.dataframe(user_data, use_container_width=True, hide_index=True)

# ======================

# EDIT RESULTS

# ======================

elif mode == "Edit Results":
user_data, worksheet = load_user_data(user_name)
if user_data is None:
st.info("There are no Tournament Scores for this person.")
st.stop()

```
st.subheader(f"{user_name}'s Tournament Results")
st.dataframe(user_data, use_container_width=True, hide_index=True)

# Select tournament to edit
tourneys_entered = user_data["Tournament Name"].tolist()
selected_edit = st.selectbox("Select Tournament to Edit:", [""] + tourneys_entered)
if not selected_edit:
    st.stop()

row_to_edit = user_data[user_data["Tournament Name"] == selected_edit].index[0] + 2
old_row = user_data.iloc[row_to_edit - 2]

st.subheader("Edit Results")
updated_results = {}
for event in events:
    if old_row["Type"] == "Class C":
        updated_results[event] = st.number_input(f"{event} (Points)", min_value=0, value=int(old_row[event]), step=1)
    else:
        places = ["", "1st", "2nd", "3rd"]
        current_place = [k for k, v in POINTS_MAP.get(old_row["Type"], {}).items() if v == int(old_row[event])]
        updated_results[event] = st.selectbox(
            f"{event} (Place)",
            places,
            index=places.index(current_place[0]) if current_place else 0,
            key=f"edit_{event}"
        )

if st.button("💾 Save Edits"):
    new_row = [old_row["Date"], old_row["Type"], old_row["Tournament Name"]]
    for event in events:
        if old_row["Type"] == "Class C":
            new_row.append(updated_results[event])
        else:
            new_row.append(POINTS_MAP.get(old_row["Type"], {}).get(updated_results[event], 0))
    worksheet.delete_row(row_to_edit)
    all_rows = worksheet.get_all_values()
    insert_idx = 2
    for i, row in enumerate(all_rows[1:], start=2):
        if row[0] > old_row["Date"]:
            insert_idx = i
            break
    else:
        insert_idx = len(all_rows) + 1
    worksheet.insert_row(new_row, insert_idx)
    update_totals(worksheet, events)
    st.success("✅ Tournament results updated successfully, totals recalculated!")
```
