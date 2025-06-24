import streamlit as st
import pandas as pd
import os
import urllib.parse
from datetime import datetime, timedelta
import dateutil.relativedelta



# Load data from the spreadsheet
def load_data(csv_path):
    """Load data from the CSV file."""
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    else:
        st.error(f"CSV file not found: {csv_path}")
        return pd.DataFrame()

# Save updated data back to the spreadsheet
def save_data(data, csv_path):
    """Save updated data to the CSV file."""
    data.to_csv(csv_path, index=False)

CSV_PATH = "extracted_ops.csv"
SCREENSHOTS_FOLDER = "./Screenshots/FirstPages"

def main():
    st.title("Decision Review App")

    # Initialize session state
    if "stage" not in st.session_state:
        st.session_state.stage = "division"

    data = load_data(CSV_PATH)

    if data.empty:
        st.stop()

    undecided_rows = data[data["Division"].isna()]

    if st.session_state.stage == "division":
        if undecided_rows.empty:
            st.success("All decisions have been assigned to a division!")
            if st.button("Let's start identifying compliance paragraphs"):
                st.session_state.stage = "compliance"
                st.experimental_rerun()
            st.stop()

        current_row = undecided_rows.iloc[0]
        decision_number = current_row["Decision Number"]
        screenshot_path = current_row.get("First Page Screenshot", None)
        pdf_path = current_row["File Path"]

        st.subheader(f"Review Decision: {decision_number}")

        divisions = ["", "Energy Division", "Icomp", "Water Division", "Communications Division", "AUDITS", "CAB", "CPED", "Executive", "PAO", "Rail Safety", "Safety Enforcement Division", "Safety Policy Division", "Transportation", "Water"]
        current_division = current_row.get("Division", "")  # Default to blank if missing
        if pd.isna(current_division) or current_division not in divisions:
            current_division = ""  # Ensure it defaults to blank

        selected_division = st.selectbox("Assign Division", divisions, index=divisions.index(current_division))

        if st.button("Update Division and Proceed"):
            data.loc[data["Decision Number"] == decision_number, "Division"] = selected_division
            save_data(data, CSV_PATH)
            st.experimental_rerun()

        if pdf_path and isinstance(pdf_path, str) and os.path.exists(pdf_path):
            absolute_path = os.path.abspath(pdf_path).replace("\\", "/")
            st.markdown(f"[Open PDF File](file:///{absolute_path})", unsafe_allow_html=True)
        else:
            st.warning(f"PDF file not found for Decision {decision_number}")

        if screenshot_path and os.path.exists(screenshot_path):
            st.image(screenshot_path, caption=f"First Page of Decision {decision_number}", use_column_width=True)
        else:
            st.warning(f"Screenshot not available for Decision {decision_number}")




# Define division keywords dictionary
    division_keywords = {
        "Energy Division": ["energy division"],
        "Water Division": ["water division"],
        "Utility Audits Risk and Compliance Division (UARCD)": ["utility audits risk and compliance division", "uarcd"],
        "Consumer Protection and Enforcement Division (CPED)": ["consumer protection and enforcement division", "cped"],
        "Rail Division": ["rail division"],
        "Communications Division": ["communications division"],
        "Safety Policy Division": ["safety policy division"],
        "Safety Enforcement Division": ["safety enforcement division"],
        "Executive Director": ["executive director"]
    }

    # Compliance Paragraph Identification Stage
    if st.session_state.stage == "compliance":
        st.title("Compliance Paragraph Identification")

        # Ensure required columns exist in the data
        required_columns = ["Compliance Paragraph", "Extraction Error", "Compliance Deadline", "Fiscal Item", "Fiscal Type", "Divisions Mentioned in OP", "Division"]
        for column in required_columns:
            if column not in data.columns:
                data[column] = None

        undecided_compliance = data[data["Compliance Paragraph"].isna()]

        if undecided_compliance.empty:
            st.success("All paragraphs have been reviewed for compliance!")
            st.session_state.stage = "error_review"  # Switch to error review stage
            st.experimental_rerun()

        current_row = undecided_compliance.iloc[0]
        decision_number = current_row["Decision Number"]
        op_text = current_row.get("Text", "")
        screenshot_path = current_row.get("Screenshot Path", None)
        issuance_date = current_row.get("Issuance Date", "")
        current_division = current_row.get("Division", None)

        # Parse issuance date
        try:
            issuance_date_parsed = datetime.strptime(issuance_date, "%m/%d/%Y")
        except ValueError:
            issuance_date_parsed = None

        # Display decision number and default assigned division
        st.subheader(f"Decision: {decision_number}")
        st.write(f"**Default Assigned Division**: {current_division}")
        st.text_area("Ordering Paragraph Text", value=op_text, height=200, disabled=True)

        # Button to mark as not a compliance paragraph
        if st.button("This is not a compliance paragraph", key=f"no_{current_row.name}"):
            data.loc[data.index == current_row.name, "Compliance Paragraph"] = "No"
            save_data(data, CSV_PATH)
            st.experimental_rerun()

        # Inputs for additional fields (always visible)
        st.write("Review the following options for this paragraph:")

        # Checkbox for extraction errors
        error_checkbox = st.checkbox(
            "This OP looks like it might have an error. Let's come back to it later.",
            key=f"error_{current_row.name}"
        )

        # Fiscal-related inputs
        fiscal_checkbox = st.checkbox(
            "This paragraph mentions money coming to or from the CPUC, so Fiscal should be notified.",
            key=f"fiscal_{current_row.name}"
        )

        fiscal_type = st.selectbox(
            "Select Fiscal Type:",
            options=["", "Accounts Payable", "Accounts Receivable", "User Fee"],
            key=f"fiscal_type_{current_row.name}"
        )

        # Multi-select dropdown for additional divisions
        additional_divisions = st.multiselect(
            "Select additional divisions this OP should be assigned to:",
            options=list(division_keywords.keys()),
            default=[],
            key=f"additional_divisions_{current_row.name}"
        )

        # Deadline-related inputs
        deadline_checkbox = st.checkbox(
            "This compliance paragraph has a deadline.",
            key=f"deadline_{current_row.name}"
        )

        # Only show date inputs and issuance date if the deadline checkbox is checked
        if deadline_checkbox:
            st.write(f"Issuance Date: **{issuance_date}**")
            st.write("Decisions describe dates in many ways - enter the appropriate value in **ONE** of the boxes below. Do not enter into multiple boxes.")

            compliance_date = st.text_input("Compliance deadline written in OP (MM/DD/YYYY)", key=f"date_{current_row.name}")
            days_after = st.number_input("Days after issuance", min_value=0, step=1, key=f"days_{current_row.name}")
            months_after = st.number_input("Months after issuance", min_value=0, step=1, key=f"months_{current_row.name}")
            years_after = st.number_input("Years after issuance", min_value=0, step=1, key=f"years_{current_row.name}")

            # Calculate the deadline based on input
            calculated_deadline = None

            if compliance_date:
                try:
                    calculated_deadline = datetime.strptime(compliance_date, "%m/%d/%Y")
                except ValueError:
                    st.error("Please enter a valid date in MM/DD/YYYY format.")
            elif issuance_date_parsed:
                if days_after > 0:
                    calculated_deadline = issuance_date_parsed + timedelta(days=days_after)
                elif months_after > 0:
                    calculated_deadline = issuance_date_parsed + dateutil.relativedelta.relativedelta(months=months_after)
                elif years_after > 0:
                    calculated_deadline = issuance_date_parsed + dateutil.relativedelta.relativedelta(years=years_after)

            if calculated_deadline:
                st.write(f"Calculated Deadline: **{calculated_deadline.strftime('%m/%d/%Y')}**")

        # Submit button
        if st.button("Submit"):
            # Save compliance paragraph state (defaults to "Yes" if not marked as "No")
            data.loc[data.index == current_row.name, "Compliance Paragraph"] = "Yes"

            # Save extraction error state
            data.loc[data.index == current_row.name, "Extraction Error"] = "Error" if error_checkbox else None

            # Save fiscal information
            if fiscal_checkbox:
                data.loc[data.index == current_row.name, "Fiscal Item"] = "Yes"
            else:
                data.loc[data.index == current_row.name, "Fiscal Item"] = None

            if fiscal_type:
                data.loc[data.index == current_row.name, "Fiscal Type"] = fiscal_type

            # Save deadline information
            if deadline_checkbox and calculated_deadline:
                data.loc[data.index == current_row.name, "Compliance Deadline"] = calculated_deadline.strftime("%m/%d/%Y")
            else:
                data.loc[data.index == current_row.name, "Compliance Deadline"] = None

            # Combine current division with additional divisions and save
            all_divisions = [current_division] if pd.notna(current_division) else []
            all_divisions.extend(additional_divisions)
            data.loc[data.index == current_row.name, "Division"] = ", ".join(all_divisions)

            save_data(data, CSV_PATH)
            st.experimental_rerun()

        # Display screenshot if available
        if screenshot_path and os.path.exists(screenshot_path):
            st.image(screenshot_path, caption=f"Screenshot for Ordering Paragraph in Decision {decision_number}", use_column_width=True)
        else:
            st.warning("Screenshot not available for this Ordering Paragraph.")
    elif st.session_state.stage == "error_review":
        st.title("Error Review and Editing")

        # Filter OPs where the error box was checked
        errored_ops = data[data["Extraction Error"] == "Error"]

        if errored_ops.empty:
            st.success("No OPs with errors to review!")
            st.stop()

        # Select the first OP with an error for review
        current_row = errored_ops.iloc[0]
        decision_number = current_row["Decision Number"]
        op_text = current_row.get("Text", "")
        screenshot_path = current_row.get("Screenshot Path", None)

        st.subheader(f"Decision: {decision_number}")

        # Editable text box for the OP
        updated_op_text = st.text_area(
            "Edit the Ordering Paragraph Text below:",
            value=op_text,
            height=200,
            key=f"edit_text_{current_row.name}"
        )

        # Buttons to save or skip
        col1, col2 = st.columns(2)

        with col1:
            if st.button("Save and Proceed"):
                # Update the OP text in the dataset
                data.loc[data.index == current_row.name, "Text"] = updated_op_text

                # Remove the "Error" mark after editing
                data.loc[data.index == current_row.name, "Extraction Error"] = None

                # Save changes
                save_data(data, CSV_PATH)
                st.experimental_rerun()

        with col2:
            if st.button("Skip"):
                st.experimental_rerun()

        # Display the screenshot below the buttons
        if screenshot_path and os.path.exists(screenshot_path):
            st.image(
                screenshot_path,
                caption=f"Screenshot for Ordering Paragraph in Decision {decision_number}",
                use_column_width=True
            )
        else:
            st.warning("Screenshot not available for this Ordering Paragraph.")
if __name__ == "__main__":
    main()
