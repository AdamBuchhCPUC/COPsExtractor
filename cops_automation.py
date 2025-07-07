import os
import streamlit as st

st.write("Chromium exists:", os.path.exists("/usr/bin/chromium"))
st.write("Chromedriver exists:", os.path.exists("/usr/lib/chromium/chromedriver"))

import streamlit as st
from utils import (
    clean_results_files_before_download,
    download_decision_pdfs,
    process_pdfs_and_export_to_csv,
    classify_divisions,
    ai_classify_ops,
    keyword_classify_ops
)
import streamlit as st
import pandas as pd
import os
from datetime import datetime, timedelta
import dateutil.relativedelta
from utils import load_data, save_data, keyword_classify_ops, ai_classify_ops
from io import BytesIO
import traceback



# Paths and settings
STEP4_CSV_PATH = "extracted_ops.csv"
STEP5_CSV_PATH = "./extracted_ops_with_divisions.csv"
STEP6_CSV_PATH = "./classified_ops_with_compliance.csv"
SCREENSHOTS_FOLDER = "./Screenshots/FirstPages"



def main():
    st.title("Decision Review Workflow")

    # Navigation between steps
    stage = st.sidebar.radio(
        "Select a Step",
        (
            "Step 1: Clean Voting Meeting Results List Before Downloading PDFs",
            "Step 2: Download PDFs",
            "Step 3: Extract Ordering Paragraphs",
            "Step 4: Assign Divisions",
            "Step 5: Compliance Identification",
            "Step 6: Export Compliance Results",
            "Compliance Wizard (Run all steps with one click)"
        )
    )

    # 🧙 Wizard: run everything automatically
    if stage == "Compliance Wizard (Run all steps with one click)":
        run_compliance_wizard()
        return

    # 🧾 Step 1–3
    if stage == "Step 1: Clean Voting Meeting Results List Before Downloading PDFs":
        run_step_1()
    elif stage == "Step 2: Download PDFs":
        run_step_2()
    elif stage == "Step 3: Extract Ordering Paragraphs":
        run_step_3()

    # 📄 Step 4: Assign Divisions
    elif stage == "Step 4: Assign Divisions":
        if not os.path.exists(STEP4_CSV_PATH):
            st.error("The extracted_ops.csv file is missing. Please complete earlier steps first.")
            return
        data = load_data(STEP4_CSV_PATH)
        if data.empty:
            st.error("No data available. Ensure the extracted_ops.csv contains data.")
            return
        run_step_4(data)

    # 📊 Step 5: Identify Compliance Paragraphs
    elif stage == "Step 5: Compliance Identification":
        if not os.path.exists(STEP5_CSV_PATH):
            st.error("The extracted_ops_with_divisions.csv file is missing. Please complete earlier steps first.")
            return
        data = load_data(STEP5_CSV_PATH)
        if data.empty:
            st.error("No data available. Ensure the extracted_ops_with_divisions.csv contains data.")
            return
        run_step_5(data)

    # 📤 Step 6: Export
    elif stage == "Step 6: Export Compliance Results":
        # Prefer wizard data if available
        if st.session_state.get("wizard_complete"):
            data = st.session_state.get("wizard_data")
        elif not os.path.exists(STEP6_CSV_PATH):
            st.error("The classified_ops_with_compliance.csv file is missing. Please complete earlier steps first.")
            return
        else:
            data = load_data(STEP6_CSV_PATH)

        if data.empty:
            st.error("No data available. Ensure the classified_ops_with_compliance.csv contains data.")
            return

        run_step_6(data)

def run_step_1(silent=False):
    folder_path = "./Voting Meeting Results"
    os.makedirs(folder_path, exist_ok=True)  # Ensure the folder exists

    if not silent:
        st.header("Step 1: Clean Voting Meeting Results List Before Downloading PDFs")

        st.markdown(
            "🔗 [Download voting meeting results here](https://www.cpuc.ca.gov/about-cpuc/transparency-and-reporting/cpuc-voting-meetings)"
        )

        st.info(
            "Move the voting meeting results spreadsheet(s) to the **'Voting Meeting Results'** folder, "
            "or upload them below. Then click the button to extract all decision numbers. "
            "You can manually delete any rows that don't need to be entered into COPs."
        )

        # Upload voting meeting results
        uploaded_files = st.file_uploader(
            "Upload Voting Meeting Results Excel/CSV files",
            accept_multiple_files=True,
            type=["csv", "xlsx"]
        )

        for uploaded_file in uploaded_files:
            with open(os.path.join(folder_path, uploaded_file.name), "wb") as f:
                f.write(uploaded_file.read())
            st.success(f"✅ Uploaded: {uploaded_file.name}")

        if not st.button("Extract Decision Numbers"):
            return

        log_placeholder = st.empty()

        def streamlit_log(message):
            log_placeholder.text(message)

    else:
        def streamlit_log(message):
            pass

    try:
        cleaned_files = clean_results_files_before_download(log=streamlit_log, folder_path=folder_path)

        if not silent:
            if cleaned_files:
                st.success(f"Processed {len(cleaned_files)} files. Filtered files saved in the same folder:")
                for file in cleaned_files:
                    st.write(f"- {file}")
            else:
                st.warning("No valid files were found or processed.")

    except Exception as e:
        if not silent:
            st.error(f"An error occurred: {e}")
        else:
            raise e



def run_step_2(silent=False):
    input_dir = "./Voting Meeting Results"
    output_dir = "./Downloaded Final Decisions"
    search_url = "https://docs.cpuc.ca.gov/DecisionsSearchForm.aspx"

    # *** Clear the output folder first ***
    if os.path.exists(output_dir):
        for filename in os.listdir(output_dir):
            file_path = os.path.join(output_dir, filename)
            try:
                if os.path.isfile(file_path) or os.path.islink(file_path):
                    os.unlink(file_path)  # remove file or link
                elif os.path.isdir(file_path):
                    shutil.rmtree(file_path)  # remove subdirectory
            except Exception as e:
                print(f"Failed to delete {file_path}. Reason: {e}")

    # Setup logging function for progress updates
    if not silent:
        st.header("Step 2: Download PDFs")

        st.info(
            "Click the button below to download PDFs of all decisions listed in the "
            "final_filtered_ files in the 'Voting Meeting Results' folder. "
            "This will open a Microsoft Edge window to search for the PDFs. Microsoft Edge was chosen "
            "because it was the default browser on Adam's computer. This could probably be made to work with "
            "other browsers using the appropriate Web Driver."
        )

        if not st.button("Download Decision PDFs"):
            return

        log_placeholder = st.empty()

        def streamlit_log(message):
            log_placeholder.text(message)
    else:
        def streamlit_log(message):
            print(message)  # Print progress to console in wizard mode

    try:
        results = download_decision_pdfs(input_dir, output_dir, search_url, log=streamlit_log)

        if not silent:
            st.success(f"Downloaded PDFs for {len(results['success'])} decisions!")
            st.warning(f"Failed to download {len(results['failed'])} decisions.")

            if results["failed"]:
                st.write("📥 Manually add PDFs of the following Decisions to the 'Downloaded Final Decisions' folder:")
                st.write(", ".join(results["failed"]))
        else:
            print(f"Downloaded PDFs for {len(results['success'])} decisions!")
            if results["failed"]:
                print(f"Failed to download PDFs for: {', '.join(results['failed'])}")
                raise Exception(f"Failed to download PDFs for: {', '.join(results['failed'])}")

    except Exception as e:
        if not silent:
            st.error(f"An error occurred: {e}")
            st.exception(e)  # Show full traceback in the Streamlit app
            with open("streamlit_error_log.txt", "a") as f:
                f.write(traceback.format_exc() + "\n")
        else:
            print(f"An error occurred: {e}")
            import traceback as tb
            print(tb.format_exc())
            raise e  # Bubble up error in wizard mode



def run_step_3(silent=False):
    folder_path = "./Downloaded Final Decisions"
    output_csv = "extracted_ops.csv"
    screenshots_folder = "./Screenshots"
    start_phrase = "it is ordered"
    end_phrase = "this order is effective"

    if not silent:
        st.header("Step 3: Extract Ordering Paragraphs from PDFs")

        if not st.button("Extract Ordering Paragraphs"):
            return

        log_placeholder = st.empty()

        def streamlit_log(message):
            log_placeholder.text(message)
    else:
        def streamlit_log(message):
            pass  # No UI logs in wizard mode

    try:
        processed_count = process_pdfs_and_export_to_csv(
            folder_path, start_phrase, end_phrase, output_csv, screenshots_folder, log=streamlit_log
        )
        if not silent:
            st.success(f"✅ Extraction completed. {processed_count} decisions processed.")
    except Exception as e:
        if not silent:
            st.error(f"An error occurred: {e}")
        else:
            raise e  # Allow wizard to catch and report it


def run_step_4(data = None):
    """Step 4: Assign divisions to decisions using OpenAI."""
    st.header("Step 4: Assign Divisions to Decisions")

    try:
        df = pd.read_csv(STEP4_CSV_PATH)
    except FileNotFoundError:
        st.error(f"❌ File not found: {STEP4_CSV_PATH}")
        return

    # Preprocess decision numbers
    df["Decision Number"] = df["Decision Number"].str.replace("D.", "D", regex=False).str.replace("-", "", regex=False).str.strip()

    # Show button to trigger classification
    if st.button("Identify Divisions Using ChatGPT"):
        unique_decisions = df[["Decision Number", "First Page Text"]].drop_duplicates()
        decision_batch = [
            {"decision_number": row["Decision Number"], "first_page_text": row["First Page Text"]}
            for _, row in unique_decisions.iterrows()
        ]

        st.write(f"🔍 Classifying {len(decision_batch)} decisions...")

        batch_size = 5  # Prevents token overload
        division_results = []

        for i in range(0, len(decision_batch), batch_size):
            batch = decision_batch[i:i+batch_size]
            result = classify_divisions(batch)
            
            if result:
                division_results.extend(result)
            else:
                print(f"⚠️ No result for batch {i // batch_size + 1}")

        if not division_results:
            st.warning("⚠️ No division results returned. All divisions will be set to 'Unknown'.")
            df["Division"] = "Unknown"
        else:
            division_df = pd.DataFrame(division_results)
            division_df.rename(columns={"decision_number": "Decision Number", "primary_division": "New Division"}, inplace=True)
            df = df.merge(division_df, on="Decision Number", how="left")
            df["Division"] = df["New Division"].combine_first(df.get("Division", pd.Series()))
            df.drop(columns=["New Division"], inplace=True)

            st.success("✅ Division classification complete.")
            st.dataframe(df[["Decision Number", "Division"]].drop_duplicates().head(10))

        df.to_csv("./extracted_ops_with_divisions.csv", index=False)
        st.info("💾 Saved to 'extracted_ops_with_divisions.csv'")
        return df


def run_step_5(data, method=None):
    st.header("Step 5: Compliance Paragraph Identification")

    df = data.copy()
    df["OP Number"] = df["OP Number"].astype(str)

    if method is None:
        method = st.selectbox(
            "Which method would you like to use to identify compliance paragraphs?",
            ("AI", "Keywords")
        )
        if not st.button("Identify Paragraphs"):
            return

    if method == "AI":
        st.info("🔍 Using ChatGPT to classify all OPs...")
        op_list = [
            {
                "decision_number": row["Decision Number"],
                "issuance_date": row["Issuance Date"],
                "primary_division": row["Division"],
                "op_number": row["OP Number"],
                "text": row["Text"]
            }
            for _, row in df.iterrows()
        ]

        batch_size = 20
        all_ai_results = []
        for i in range(0, len(op_list), batch_size):
            batch = op_list[i:i + batch_size]
            st.write(f"📦 Processing batch {i // batch_size + 1} of {(len(op_list) - 1) // batch_size + 1}")
            batch_results = ai_classify_ops(batch, batch_size)
            if isinstance(batch_results, dict):
                batch_results = [batch_results]
            all_ai_results.extend(batch_results)

        if all_ai_results:
            valid_results = [item for item in all_ai_results if isinstance(item, dict) and item]
            valid_results = [item for item in valid_results if item.get("decision_number") and item.get("op_number")]

            for item in valid_results:
                if (
                    item.get("deadline", "").strip().lower() == "yes"
                    and item.get("specific_action", "").strip().lower() == "yes"
                    and item.get("cpuc_notified", "").strip().lower() == "yes"
                ):
                    item["Compliance Paragraph"] = "Yes"
                else:
                    item["Compliance Paragraph"] = "No"

            ai_df = pd.DataFrame(valid_results)
            ai_df["op_number"] = ai_df["op_number"].astype(str)

            df = df.merge(
                ai_df[[
                    "decision_number", "op_number",
                    "Compliance Paragraph", "deadline", "specific_action", "cpuc_notified",
                    "due_date", "fiscal", "additional_division", "extraction_error"
                ]],
                left_on=["Decision Number", "OP Number"],
                right_on=["decision_number", "op_number"],
                how="left"
            )

            df.drop(columns=["decision_number", "op_number"], inplace=True)

            df.rename(columns={
                "due_date": "Compliance Deadline",
                "fiscal": "Fiscal Type",
                "additional_division": "Divisions Mentioned in OP",
                "extraction_error": "Extraction Error"
            }, inplace=True)
        else:
            st.error("❌ No results returned from OpenAI.")
            return

    else:
        st.info("🔍 Using keyword-based classification...")
        df["Compliance Paragraph"] = df["Text"].apply(keyword_classify_ops)
        df["deadline"] = ""
        df["specific_action"] = ""
        df["cpuc_notified"] = ""

    # Save results
    df.to_csv("classified_ops_with_compliance.csv", index=False)
    st.success("✅ Classification complete. Saved to 'classified_ops_with_compliance.csv'.")
    st.dataframe(df[[
        "Decision Number", "OP Number", "Compliance Paragraph",
        "deadline", "specific_action", "cpuc_notified"
    ]].head(10))

    return df


def run_step_6(data):
    st.header("Step 6: Export Compliance Results")

    try:
        df = pd.read_csv(STEP6_CSV_PATH)
    except FileNotFoundError:
        st.error(f"❌ File not found: {STEP6_CSV_PATH}")
        return

    if "Compliance Paragraph" not in data.columns:
        st.error("⚠️ Compliance classification has not been completed yet. Please run Step 5 first.")
        return

    st.markdown(
        "This step creates two **Excel files**:\n"
        "- ✅ One with **'Yes'** compliance paragraphs\n"
        "- ❌ One with **'No'** paragraphs to review or distribute\n"
    )

    if st.button("Generate Export Files"):
        try:
            yes_df = data[data["Compliance Paragraph"] == "Yes"]
            no_df = data[data["Compliance Paragraph"] == "No"]

            timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
            yes_filename = f"Compliance_Yes_{timestamp}.xlsx"
            no_filename = f"Compliance_No_{timestamp}.xlsx"

            # Create in-memory files
            yes_buffer = BytesIO()
            with pd.ExcelWriter(yes_buffer, engine="xlsxwriter") as writer:
                yes_df.to_excel(writer, sheet_name="Compliance_Yes", index=False)
            yes_buffer.seek(0)

            no_buffer = BytesIO()
            with pd.ExcelWriter(no_buffer, engine="xlsxwriter") as writer:
                no_df.to_excel(writer, sheet_name="Compliance_No", index=False)
            no_buffer.seek(0)

            # Save locally as backup
            with pd.ExcelWriter(yes_filename, engine="xlsxwriter") as writer:
                yes_df.to_excel(writer, sheet_name="Compliance_Yes", index=False)
            with pd.ExcelWriter(no_filename, engine="xlsxwriter") as writer:
                no_df.to_excel(writer, sheet_name="Compliance_No", index=False)

            # Save to session state so download buttons persist after rerun
            st.session_state["step6_export_ready"] = True
            st.session_state["step6_yes_buffer"] = yes_buffer
            st.session_state["step6_no_buffer"] = no_buffer
            st.session_state["step6_yes_filename"] = yes_filename
            st.session_state["step6_no_filename"] = no_filename
            st.session_state["step6_yes_df"] = yes_df
            st.session_state["step6_no_df"] = no_df

        except Exception as e:
            st.error(f"❌ An error occurred while generating export files: {e}")

    # Show download options if files are ready
    if st.session_state.get("step6_export_ready"):
        st.success("✅ Export complete! Download and upload your files below:")

        st.download_button(
            label="📥 Download 'Yes' Compliance File",
            data=st.session_state["step6_yes_buffer"],
            file_name=st.session_state["step6_yes_filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        st.download_button(
            label="📥 Download 'No' Compliance File",
            data=st.session_state["step6_no_buffer"],
            file_name=st.session_state["step6_no_filename"],
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

        # Upload instructions
        st.markdown("### 📤 Upload Instructions")
        st.markdown(
            f"- Upload **`{st.session_state['step6_yes_filename']}`** to the [Compliance Upload Folder](https://capuc.sharepoint.com/:f:/r/sites/OrderingParagraphComplianceTracking/Shared%20Documents/Ordering%20Paragraph%20Upload%20Folder?csf=1&web=1&e=BTchmf)."
        )
        st.markdown(
            f"- Upload **`{st.session_state['step6_no_filename']}`** to [this folder](YOUR_REJECTED_UPLOAD_LINK_HERE)."
        )

        with st.expander("Preview 'Yes' Paragraphs"):
            st.dataframe(st.session_state["step6_yes_df"][["Decision Number", "OP Number", "Text"]].head(10))

        with st.expander("Preview 'No' Paragraphs"):
            st.dataframe(st.session_state["step6_no_df"][["Decision Number", "OP Number", "Text"]].head(10))

def run_compliance_wizard():
    st.header("🧙 Compliance Wizard")
    st.markdown("This will automatically run Steps 1 through 5.")

    # Let user choose classification method for Step 5
    method = st.selectbox(
        "Choose how to identify compliance paragraphs in Step 5:",
        ("AI", "Keywords")
    )

    if st.button("Start Compliance Wizard"):
        try:
            # Create placeholders for live step updates
            step1_status = st.empty()
            step2_status = st.empty()
            step3_status = st.empty()
            step4_status = st.empty()
            step5_status = st.empty()

            # Step 1
            step1_status.markdown("🔄 **Running Step 1: Clean Voting Meeting Results...**")
            run_step_1(silent=True)
            step1_status.success("✅ Step 1 complete: Voting Meeting Results cleaned.")

            # Step 2
            step2_status.markdown("🔄 **Running Step 2: Download Decision PDFs...**")
            run_step_2(silent=True)
            step2_status.success("✅ Step 2 complete: PDFs downloaded.")

            # Step 3
            step3_status.markdown("🔄 **Running Step 3: Extract Ordering Paragraphs...**")
            run_step_3(silent=True)
            step3_status.success("✅ Step 3 complete: Ordering Paragraphs extracted.")

            # Load data for Steps 4–5
            if not os.path.exists(CSV_PATH):
                st.error("❌ Could not find extracted_ops.csv. Something went wrong in Steps 1–3.")
                return

            data = load_data(CSV_PATH)
            if data.empty:
                st.error("❌ extracted_ops.csv is empty.")
                return

            # Step 4
            step4_status.markdown("🔄 **Running Step 4: Assign Divisions...**")
            data = run_step_4(data)
            step4_status.success("✅ Step 4 complete: Divisions assigned.")

            # Step 5
            step5_status.markdown(f"🔄 **Running Step 5: Compliance Identification using {method}...**")
            data = run_step_5(data, method=method)
            step5_status.success("✅ Step 5 complete: Compliance Paragraphs identified.")

            # Save session for Step 6
            st.session_state["wizard_complete"] = True
            st.session_state["wizard_data"] = data

            st.success("🎉 Wizard complete! You can now proceed to Step 6 to export the results.")

        except Exception as e:
            st.error(f"❌ An error occurred while running the wizard: {e}")

if __name__ == "__main__":
    main()
