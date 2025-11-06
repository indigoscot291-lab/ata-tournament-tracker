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

    st.session_state.mode = ""  # Reset to main menu
    st.experimental_rerun()     # Force UI refresh
