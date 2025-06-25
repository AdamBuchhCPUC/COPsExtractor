import os
import pandas as pd
import io

def clean_results_files_before_download(log, folder_path: str, encoding: str = "ISO-8859-1") -> list:
    """
    Cleans CSV files in a folder by:
      - Identifying the header row starting with 'Item #' and 'Agenda ID'.
      - Filtering rows where "Decision Number" starts with 'D'.
      - Further filtering rows where "Outcome" is "Signed" or "Signed as Modified".
    
    Args:
        folder_path (str): Path to the folder containing the CSV files.
        encoding (str): File encoding to use when reading the files.

    Returns:
        list: Paths of the successfully cleaned and filtered CSV files.
    """
    cleaned_files = []

    for file_name in os.listdir(folder_path):
        if file_name.endswith(".csv") and not file_name.startswith(("cleaned_", "final_filtered_")):
            file_path = os.path.join(folder_path, file_name)
            try:
                # Read the file with the correct encoding
                with open(file_path, "r", encoding=encoding) as file:
                    lines = file.readlines()

                # Locate the header row containing 'Item #' and remove preceding rows
                header_index = None
                for i, line in enumerate(lines):
                    if "Item #" in line and "Agenda ID" in line:
                        header_index = i
                        break

                # Skip rows until the header row
                if header_index is not None:
                    cleaned_lines = lines[header_index:]
                    cleaned_data = "".join(cleaned_lines)
                    df = pd.read_csv(io.StringIO(cleaned_data), encoding=encoding)
                else:
                    log(f"Header row not found in file: {file_name}")
                    continue

                # Filter rows where "Decision Number" starts with 'D'
                if "Decision Number" in df.columns:
                    df_filtered = df[df["Decision Number"].astype(str).str.lower().str.startswith("d")]
                else:
                    log(f"'Decision Number' column not found in file: {file_name}")
                    continue

                # Warn about rows where "Outcome" is not "Signed" or "Signed as Modified"
                if "Outcome" in df_filtered.columns:
                    valid_outcomes = ["signed", "signed as modified"]
                    not_signed = df_filtered[~df_filtered["Outcome"].str.lower().isin(valid_outcomes)]
                    if not not_signed.empty:
                        log(f"Warning: File '{file_name}' contains rows with 'Outcome' not equal to valid outcomes:")
                        for _, row in not_signed.iterrows():
                            log(f"Decision Number: {row['Decision Number']}, Outcome: {row['Outcome']}")

                    # Filter rows with valid outcomes
                    df_final = df_filtered[df_filtered["Outcome"].str.lower().isin(valid_outcomes)]
                else:
                    log(f"'Outcome' column not found in file: {file_name}")
                    continue

                # Save the final filtered DataFrame
                final_file_path = os.path.join(folder_path, f"final_filtered_{file_name}")
                df_final.to_csv(final_file_path, index=False, encoding=encoding)
                cleaned_files.append(final_file_path)

                log(f"Processed and saved filtered results for file: {file_name}")

            except Exception as e:
                log(f"An error occurred while processing file {file_name}: {e}")

    return cleaned_files

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.chrome.options import Options

from webdriver_manager.chrome import ChromeDriverManager
import pandas as pd
import requests
import re
import os

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options

def get_chrome_driver():
    chrome_options = Options()
    chrome_options.binary_location = "/usr/bin/chromium"  # ✅ Correct for Debian
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--window-size=1920x1080")

    service = Service("/usr/lib/chromium/chromedriver")  # ✅ Matches installed chromium-driver

    return webdriver.Chrome(service=service, options=chrome_options)

def download_decision_pdfs(input_dir: str, output_dir: str, search_url: str, log, max_retries: int = 3) -> dict:
    os.makedirs(output_dir, exist_ok=True)

    csv_files = [os.path.join(input_dir, file) for file in os.listdir(input_dir) if file.startswith("final_filtered_") and file.endswith(".csv")]

    decision_numbers = []
    for csv_file in csv_files:
        try:
            df = pd.read_csv(csv_file, encoding='utf-8')
        except UnicodeDecodeError:
            log(f"Encoding issue with {csv_file}. Retrying with ISO-8859-1...")
            df = pd.read_csv(csv_file, encoding='ISO-8859-1')

        if "Decision Number" in df.columns:
            cleaned_numbers = df["Decision Number"].dropna().apply(lambda x: re.sub(r'[^\d]', '', str(x))).tolist()
            decision_numbers.extend(cleaned_numbers)
        else:
            log(f"Warning: 'Decision Number' column not found in {csv_file}.")

    decision_numbers = list(set(decision_numbers))
    if not decision_numbers:
        log("No valid decision numbers found.")
        return {"success": [], "failed": [], "total": 0}

    successful_downloads = []
    failed_decisions = []

    log(f"Found {len(decision_numbers)} unique decision numbers to process.")

    def is_error_page(driver):
        try:
            error_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            return ("an unhandled exception occurred" in error_text or "the process cannot access the file" in error_text)
        except Exception:
            return False

    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--window-size=1920x1080")

    service = Service(ChromeDriverManager().install())
    driver = get_chrome_driver()
    driver.get(search_url)

    decision_count = 0
    try:
        for decision_number in decision_numbers:
            log(f"Processing decision number {decision_count + 1}/{len(decision_numbers)}: {decision_number}")
            if decision_count > 0 and decision_count % 50 == 0:
                log("Restarting WebDriver to free resources...")
                driver.quit()
                service = Service(ChromeDriverManager().install())
                driver = get_chrome_driver()
                driver.get(search_url)

            retries = 0
            success = False

            while retries < max_retries:
                try:
                    search_box = WebDriverWait(driver, 10).until(
                        EC.visibility_of_element_located((By.ID, "DocTitle"))
                    )
                    search_box.clear()
                    search_box.send_keys(decision_number)
                    search_box.send_keys(Keys.RETURN)

                    WebDriverWait(driver, 20).until(
                        EC.presence_of_element_located((By.ID, "ResultTable"))
                    )

                    if is_error_page(driver):
                        log(f"Error page detected for decision {decision_number}. Retrying...")
                        retries += 1
                        driver.refresh()
                        continue

                    results_table = driver.find_element(By.ID, "ResultTable")
                    rows = results_table.find_elements(By.XPATH, ".//tbody/tr[not(@style='height:1px')]")
                    downloaded_pdf = False

                    for row in rows:
                        try:
                            result_title_td = row.find_element(By.CLASS_NAME, "ResultTitleTD")
                            result_title_id = re.sub(r'[^\w\d]', '_', result_title_td.text.split("\n")[0].strip())

                            pdf_links = row.find_elements(By.XPATH, ".//a[contains(translate(@href, 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '.pdf')]")
                            for pdf_link in pdf_links:
                                pdf_url = pdf_link.get_attribute("href")
                                pdf_response = requests.get(pdf_url, stream=True)
                                pdf_filename = os.path.join(output_dir, f"{result_title_id}.pdf")
                                with open(pdf_filename, "wb") as pdf_file:
                                    pdf_file.write(pdf_response.content)
                                log(f"Downloaded PDF: {pdf_filename}")
                                downloaded_pdf = True

                            if not pdf_links:
                                log(f"No PDF link found for row with title: {result_title_id}")
                        except Exception as e:
                            log(f"Error processing a result row: {e}")

                    if downloaded_pdf:
                        successful_downloads.append(decision_number)
                    else:
                        failed_decisions.append(decision_number)

                    success = True
                    break

                except WebDriverException as e:
                    log(f"WebDriver error for decision number {decision_number}: {e}")
                    retries += 1
                    driver.refresh()

                except Exception as e:
                    log(f"Error processing decision number {decision_number}: {e}")
                    retries += 1
                    with open(f"error_page_{decision_number}.html", "w", encoding="utf-8") as f:
                        f.write(driver.page_source)

            if not success:
                log(f"Failed to process decision number {decision_number} after {max_retries} retries.")
                failed_decisions.append(decision_number)

            try:
                driver.get(search_url)
                WebDriverWait(driver, 10).until(
                    EC.presence_of_element_located((By.ID, "DocTitle"))
                )
            except Exception as e:
                log(f"Error navigating back to search page for decision {decision_number}: {e}")
                failed_decisions.append(decision_number)

            decision_count += 1
    finally:
        driver.quit()

    total_decisions = len(decision_numbers)
    successful_count = len(successful_downloads)
    failure_count = len(failed_decisions)

    log("\nSummary:")
    log(f"Total decision numbers processed: {total_decisions}")
    log(f"Successful downloads: {successful_count} ({(successful_count / total_decisions) * 100:.2f}%)")
    log(f"Failed to download: {failure_count} ({(failure_count / total_decisions) * 100:.2f}%)")
    log(f"\nManually add PDFs of the following final decisions to the 'Downloaded Final Decisions' folder before extracting ordering paragraphs:")
    log(f"Decision Numbers: " + str(failed_decisions))

    return {
        "success": successful_downloads,
        "failed": failed_decisions,
        "total": total_decisions,
    }


import pdfplumber
import re
import os
import csv
from collections import defaultdict
import shutil

def clear_folder(folder_path, log):
    """Delete all files in the specified folder, but keep subfolders and the folder itself."""
    if os.path.exists(folder_path):
        for root, _, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                try:
                    os.remove(file_path)  # Remove file
                except Exception as e:
                    log(f"Error deleting file {file_path}: {e}")

def load_data(csv_path):
    """Load data from the specified CSV file."""
    if os.path.exists(csv_path):
        return pd.read_csv(csv_path)
    else:
        return pd.DataFrame()

def save_data(data, csv_path):
    """Save DataFrame to the specified CSV file."""
    data.to_csv(csv_path, index=False)

# Extract text from the first page of a PDF and save a screenshot
def save_first_page_screenshot(pdf_path, first_page_folder, log):
    os.makedirs(first_page_folder, exist_ok=True)
    pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]
    screenshot_path = os.path.join(first_page_folder, f"{pdf_basename}_first_page.png")
    try:
        with pdfplumber.open(pdf_path) as pdf:
            if len(pdf.pages) > 0:
                pdf.pages[0].to_image().save(screenshot_path)
    except Exception as e:
        log(f"Error saving first page screenshot for {pdf_path}: {e}")
        screenshot_path = None  # Return None if there was an error
    return screenshot_path

# Functions for Metadata Extraction
def extract_first_page_text_from_pdf(pdf_path):
    """Extract text from the first two pages of a PDF file."""
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages_to_extract = min(2, len(pdf.pages))
            text = "\n".join(pdf.pages[i].extract_text() or "" for i in range(pages_to_extract))
    except Exception as e:
        print(f"Error reading {pdf_path}: {e}")
    return clean_text(text)


def extract_date_of_issuance(text):
    """Extract the Date of Issuance from the text."""
    match = re.search(
        r"Date\s*of\s*issuance[:\s]*(\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]+\s+\d{1,2},\s+\d{4})",
        text,
        re.IGNORECASE
    )
    return match.group(1) if match else None

def extract_decision_number(text):
    """Extract the Decision number from the text."""
    match = re.search(r"Decision\s+(\d{2}-\d{2}-\d{3})", text, re.IGNORECASE)
    return f"D.{match.group(1)}" if match else None

def extract_proceedings_and_related_matters(text):
    """Extract the first proceeding and related matters from the text, removing duplicates."""
    matches = re.findall(r"(?:Application|Rulemaking|Case)\s+\d{2}-\d{2}-\d{3}", text, re.IGNORECASE)
    unique_matches = list(dict.fromkeys(matches))  # Remove duplicates while maintaining order
    primary_proceeding = unique_matches[0] if unique_matches else None
    related_matters = unique_matches[1:] if len(unique_matches) > 1 else []
    return primary_proceeding, related_matters

# Function to Replace Odd Characters
def clean_text(text):
    """Replaces odd characters with their correct counterparts."""
    replacements = {
        "â€œ": '"',
        "â€": '"',
        "â€™": "'",
        "â€“": "–",
        "â€”": "—",
        "â€¦": "…",
        "Ã©": "é",  # Example for accented e
    }
    for odd_char, correct_char in replacements.items():
        text = text.replace(odd_char, correct_char)
    return text

# Function to Extract OPs from PDF
def extract_text_between_phrases_and_split(pdf_path, start_phrase, end_phrase, screenshots_folder, log):
    extracted_paragraphs = []
    capturing = False
    buffer = []
    current_op_text = []
    current_op_number = None
    expected_op_number = 1

    # Dictionary to track screenshots by page
    page_screenshot_map = defaultdict(str)

    # Open the PDF
    with pdfplumber.open(pdf_path) as pdf:
        pdf_basename = os.path.splitext(os.path.basename(pdf_path))[0]

        for page_number, page in enumerate(pdf.pages):
            text = clean_text(page.extract_text() or "")  # Clean extracted text
            if not text:
                continue

            # Normalize text for consistent processing
            lines = text.split("\n")
            for line_number, line in enumerate(lines):
                # Check for start phrase (case-insensitive)
                if start_phrase.lower() in line.lower():
                    capturing = True
                    continue  # Skip the start phrase line

                # Check for end phrase (case-insensitive)
                if capturing and end_phrase.lower() in line.lower():
                    capturing = False
                    break  # Stop capturing further

                # Capture text if within the target section
                if capturing:
                    buffer.append((page_number, line_number, line))  # Track page and line number

        # Extract OPs and capture screenshots
        current_op_region = None
        for page_number, line_number, line in buffer:
            line = clean_text(line)  # Clean text for odd characters
            op_match = re.match(r"(?m)^(\d+)\.\s", line)

            if op_match:
                op_number = int(op_match.group(1))

                # If the number matches the expected sequence, start a new OP
                if op_number == expected_op_number:
                    if current_op_text:
                        # Link to the existing screenshot for this page
                        screenshot_path = page_screenshot_map.get(page_number)
                        extracted_paragraphs.append((current_op_number, " ".join(current_op_text), screenshot_path))

                    current_op_text = [line.strip()]
                    current_op_number = f"{op_number}."
                    expected_op_number += 1

                    # Save a screenshot for this page if not already saved
                    if page_number not in page_screenshot_map:
                        screenshot_path = os.path.join(
                            screenshots_folder, f"{pdf_basename}_page_{page_number + 1}.png"
                        )
                        save_screenshot(pdf_path, page_number, screenshot_path)
                        page_screenshot_map[page_number] = screenshot_path

                else:
                    # If the number doesn't match the sequence, treat as part of the current OP
                    current_op_text.append(line.strip())
            else:
                # Append any non-matching lines to the current OP
                current_op_text.append(line.strip())

        # Append the last OP
        if current_op_text:
            screenshot_path = page_screenshot_map.get(page_number)
            extracted_paragraphs.append((current_op_number, " ".join(current_op_text), screenshot_path))

    return extracted_paragraphs

def save_screenshot(pdf_path, page_number, screenshot_path):
    """Save a screenshot of a specified page from the PDF."""
    with pdfplumber.open(pdf_path) as doc:
        page = doc.pages[page_number]
        cropped_image = page.to_image()
        cropped_image.save(screenshot_path)

# Enhanced processing function
def process_pdfs_and_export_to_csv(folder_path, start_phrase, end_phrase, output_csv, screenshots_folder, log):
    # Clear Screenshots folder
    clear_folder(screenshots_folder, log)
    first_page_folder = os.path.join(screenshots_folder, "FirstPages")
    os.makedirs(first_page_folder, exist_ok=True)

    processed_count = 0
    no_op_decisions = []  # List to track decisions with no ordering paragraphs

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

    with open(output_csv, mode="w", newline="", encoding="utf-8") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow([
            "Decision Number", "Issuance Date", "Proceeding", "Related Matters", 
            "File Title", "File Path", "First Page Text", "First Page Screenshot", "Division", "Fiscal", 
            "OP Number", "Text", "Division Mentioned in OP", "Screenshot Path"
        ])

        for file_name in os.listdir(folder_path):
            if file_name.endswith(".pdf"):
                pdf_path = os.path.join(folder_path, file_name)
                log(f"Processing: {pdf_path}")

                # Save first page screenshot
                first_page_screenshot = save_first_page_screenshot(pdf_path, first_page_folder, log)

                # Extract metadata from the first page
                first_page_text = extract_first_page_text_from_pdf(pdf_path)
                decision_number = extract_decision_number(first_page_text)
                issuance_date = extract_date_of_issuance(first_page_text)
                primary_proceeding, related_matters = extract_proceedings_and_related_matters(first_page_text)

                # Determine the "Division" based on the presence of "Intervenor compensation"
                division = "Icomp" if "intervenor compensation" in first_page_text.lower() else ""

                # Extract OPs and screenshots
                try:
                    ops = extract_text_between_phrases_and_split(pdf_path, start_phrase, end_phrase, screenshots_folder, log)
                except Exception as e:
                    log(f"Error processing OPs for {file_name}: {e}")
                    continue

                # If no ordering paragraphs, add the decision to the no_op_decisions list
                if not ops:
                    no_op_decisions.append(decision_number or file_name)

                # Write data for each OP
                for op_number, op_text, screenshot_path in ops:
                    # Check if any division keywords are mentioned in the text
                    mentioned_divisions = []
                    for division_name, keywords in division_keywords.items():
                        if any(keyword.lower() in op_text.lower() for keyword in keywords):
                            mentioned_divisions.append(division_name)

                    # Join mentioned divisions into a single string
                    division_mentioned = "; ".join(mentioned_divisions) if mentioned_divisions else "None"

                    writer.writerow([
                        decision_number or "N/A",
                        issuance_date or "N/A",
                        primary_proceeding or "N/A",
                        "; ".join(related_matters) if related_matters else "N/A",
                        file_name,
                        pdf_path,
                        first_page_text,
                        first_page_screenshot or "N/A",  # Add first-page screenshot path
                        division,  # Set "Division" column
                        "N/A",  # Placeholder for Fiscal
                        op_number,
                        op_text,
                        division_mentioned,  # New column for divisions mentioned
                        screenshot_path
                    ])

                processed_count += 1

    # Output the list of decisions with no ordering paragraphs
    if no_op_decisions:
        log("\nWarning: The following decisions had no ordering paragraphs. You can add them manually to the extracted_ops file:")
        for decision in no_op_decisions:
            log(f"- {decision}")
    
    log(f"\nExtraction completed. {processed_count} decisions processed.")
    return processed_count
# Example usage
folder_path = "./Downloaded Final Decisions"
start_phrase = "it is ordered"
end_phrase = "this order is effective"
output_csv = "extracted_ops.csv"
screenshots_folder = "./Screenshots"


# log(f"Results saved to {output_csv}. Screenshots saved to {screenshots_folder}.")

import openai
import json
import pandas as pd
import streamlit as st

api_key = st.secrets.get("OPENAI_API_KEY", None)

if not api_key:
    st.error("🚨 Missing OpenAI API key. Please add it to Streamlit secrets.")
else:
    openai.api_key = api_key

client = openai.OpenAI(api_key=api_key)


# 🔹 Division Classifier
def classify_divisions(batch):
    prompt = f"""
    You are analyzing CPUC decisions to assign the correct primary division based on the first page of each decision.
    Choose from:
    - Energy Division
    - Water Division
    - Utility Audits Risk and Compliance Division (UARCD)
    - Consumer Protection and Enforcement Division (CPED)
    - Rail Division
    - Communications Division
    - Safety Policy Division
    - Safety Enforcement Division
    - Executive Director
    - Consumer Affairs Branch

    For each decision, return JSON with:
    - "decision_number"
    - "primary_division"

    Decisions:
    {json.dumps(batch, indent=2)}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        return json.loads(response.choices[0].message.content)
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        return []

# Function to check compliance conditions
def check_compliance(text):
    if pd.isna(text):  # Handle NaN values
        return "No"
    
    # Ignore "shall be filed under seal" and "shall be exempt"
    text = re.sub(r"shall be filed under seal", "", text, flags=re.IGNORECASE)
    text = re.sub(r"shall be exempt", "", text, flags=re.IGNORECASE)
    text = re.sub(r"will be considered", "", text, flags=re.IGNORECASE)
    text = re.sub(r"shall be consolidated", "", text, flags=re.IGNORECASE)
    text = re.sub(r"will expire", "", text, flags=re.IGNORECASE)
    text = re.sub(r"shall remain under seal", "", text, flags=re.IGNORECASE)
    
    # Check for "shall", "must", "is ordered to", "is hereby directed", "is responsible for timely reporting and remittance", or "is directed to"
    if (re.search(r"\bshall\b", text, re.IGNORECASE) or 
        re.search(r"\bmust\b", text, re.IGNORECASE) or 
        re.search(r"\bis ordered to\b", text, re.IGNORECASE) or 
        re.search(r"\bis hereby directed\b", text, re.IGNORECASE) or 
        re.search(r"\bis responsible for timely reporting and remittance\b", text, re.IGNORECASE) or 
        re.search(r"\bwill\b", text, re.IGNORECASE) or
        re.search(r"\bis responsible for\b", text, re.IGNORECASE) or
        re.search(r"\bwe order\b", text, re.IGNORECASE) or
        re.search(r"\bwe further order\b", text, re.IGNORECASE) or
        re.search(r"\bare directed to\b", text, re.IGNORECASE) or
        re.search(r"\bare required to provide\b", text, re.IGNORECASE) or
        re.search(r"\bshall be\b", text, re.IGNORECASE) or
        re.search(r"\bis directed to\b", text, re.IGNORECASE)):
        return "Yes"
    return "No"


def ai_classify_ops(op_batch, batch_size):
    prompt = f"""
    You are analyzing CPUC Ordering Paragraphs (OPs).
    For each OP, classify the following:

    1. Does this ordering paragraph include reference to a deadline, including recurring ones such as quarterly or annual reports or filings? ("Yes" or "No")
       Example: " no later than December 1, 2026." → Yes
       Example: "shall submit this data with their annual report." → Yes
       Example: "within 15 days/2 months/1 year etc of the date of this decision" → Yes
       Example: "timely submission" → Yes
       Example: "five days prior to..." → Yes
       Example: "Along with the Quarterly Water Cost and Bill Tracker, San Gabriel Valley Water Company 
       shall update the affordability tables..."  → Yes
       Example: "San Gabriel Water Company shall file a Tier 2 advice letter outlining the costs it will include in rates.   
       The revised tariff schedule must take effect no earlier than July 1, 2024 and July 1, 2025, respectively"  → Yes
       Example: Kcindur Communications, Inc. dba Advanced Wireless must file in this docket a written acceptance of the certificate granted in this proceeding within 30 days of the effective date of this decision. 
       The written acceptance filed in this docket does not reopen the proceeding." → Yes
        Kcindur Communications, Inc. dba Advanced Wireless must provide the name, address, e-mail address, 
        and telephone number of its designated primary regulatory/official contact person to the California 
        Public Utilities Commissionâ€™s Communications Division within five (5) days of written acceptance 
        of its certificate."  → Yes 
       Counter-Example: "This decision becomes effective today." → No


    2. Does this ordering paragraph require a specific action by the regulated entity? ("Yes" or "No")
       Example: "PG&E shall file a Tier 1 Advice Letter incorporating the rules listed in Appendix A no later than December 1, 2026." → Yes
       Example 2: "3. The motions filed by WRA II Pioneer (S) LLC and Intermountain Infrastructure Group, LLC (Joint Applicants), for leave to 
       file confidential 
       information under seal, contained in: 1) Application 23-03-004, Exhibits E, H, and I; and 
       2) Attachment 1 to Joint Applicants May 1, 2023 response to a ruling requesting information, is granted. 
       These documents shall remain under seal for three years after the date of this order. During this three-year period, 
       the confidential materials shall remain under seal and not be accessible or disclosed to persons other than the Commissioners 
       and Commission staff except on further order or ruling of the Commission, the assigned Administrative Law Judge, or the designated
        Law and Motion Judge at the time of such ruling. If any interested party believes it is necessary for any of this information to 
        remain under seal longer than three years, that party shall file a new motion stating the justification - 12 - A.23-03-004 ALJ/SMW/SRM/smt 
        of further withholding the information from public inspection. The motion shall be filed at least 30 days before expiration of the instant order." → No 
        Example: "Along with the Quarterly Water Cost and Bill Tracker, San Gabriel Valley Water Company shall update the affordability tables using the 2022 Affordability Annual Refresh submitted in this proceeding." → Yes
       Counter-Example: "PG&E is authorized to charge $35,000 to the RSBT balancing account." → No
       Counter-Example: "PG&E is authorized to administratively process remaining invoices and pay final authorized expenses related to the DRAM pilot program through 2025, and to perform any final true-up 
       accounting for DRAM through its 2026 Annual Electric True-Up Advice Letter submission." → No (Explanation: something that is authorized is not required)

    3. Will the CPUC be notified of this action? ("Yes" or "No")  
       This includes situations where the paragraph mentions the filing of a report, advice letter, notice, or where Commission staff or a public workshop is involved.
       Example: "SCE shall serve a copy of the report on the Energy Division." → Yes  
       Example: "Within five days of the effective date of this decision, PacifiCorp d/b/a Pacific Power (PacifiCorp) shall file a Tier 1 Advice Letter with tariff details" → Yes 
       Example: "Along with the Quarterly Water Cost and Bill Tracker, San Gabriel Valley Water Company shall update the affordability tables using the 2022 Affordability 
       Annual Refresh submitted in this proceeding." → Yes (Explanation: the word "quarterly" here indicates a regularly-updated report)
       Example: "A public workshop shall be held within 30 days of the effective date." → Yes  
       Counter-Example: "PG&E is ordered to implement the program within 90 days." → No
       Example: "4. Kcindur Communications, Inc. dba Advanced Wireless must file in this docket a written acceptance of the certificate granted in this proceeding within 30 days of the effective date of this decision. 
       The written acceptance filed in this docket does not reopen the proceeding."→ Yes  (explanation: a docket filing is another term for a notification to the CPUC)

    4. Due Date: If mentioned, or calculate relative to issuance date (e.g., "30 days after 01/01/2025" → "01/31/2025").
    5. Fiscal Impact? ("Accounts Payable", "Accounts Receivable", "User Fee", or "No").
    6. Additional Division(s): If a CPUC division or branch is mentioned, list it.
    7. Extraction Error? ("Error" if incomplete, otherwise "No Error").

    Return JSON for each OP:
    - "decision_number"
    - "op_number"
    - "deadline"
    - "specific_action"
    - "cpuc_notified"
    - "due_date"
    - "fiscal"
    - "additional_division"
    - "extraction_error"

    OPs:
    {json.dumps(op_batch, indent=2)}
    """
    try:
        response = client.chat.completions.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.2
        )
        model_output = response.choices[0].message.content
        return json.loads(model_output)
    except Exception as e:
        print(f"Error during OpenAI API call: {e}")
        if len(op_batch) > 1:
            print("Retrying with smaller batches...")
            mid = len(op_batch) // 2
            return classify_op_batch(op_batch[:mid], batch_size) + classify_op_batch(op_batch[mid:], batch_size)
        return []

# Function to check compliance conditions
def keyword_classify_ops(text):
    if pd.isna(text):  # Handle NaN values
        return "No"
    
    # Ignore "shall be filed under seal" and "shall be exempt"
    text = re.sub(r"shall be filed under seal", "", text, flags=re.IGNORECASE)
    text = re.sub(r"shall be exempt", "", text, flags=re.IGNORECASE)
    text = re.sub(r"will be considered", "", text, flags=re.IGNORECASE)
    text = re.sub(r"shall be consolidated", "", text, flags=re.IGNORECASE)
    text = re.sub(r"will expire", "", text, flags=re.IGNORECASE)
    text = re.sub(r"shall remain under seal", "", text, flags=re.IGNORECASE)
    
    # Check for "shall", "must", "is ordered to", "is hereby directed", "is responsible for timely reporting and remittance", or "is directed to"
    if (re.search(r"\bshall\b", text, re.IGNORECASE) or 
        re.search(r"\bmust\b", text, re.IGNORECASE) or 
        re.search(r"\bis ordered to\b", text, re.IGNORECASE) or 
        re.search(r"\bis hereby directed\b", text, re.IGNORECASE) or 
        re.search(r"\bis responsible for timely reporting and remittance\b", text, re.IGNORECASE) or 
        re.search(r"\bwill\b", text, re.IGNORECASE) or
        re.search(r"\bis responsible for\b", text, re.IGNORECASE) or
        re.search(r"\bwe order\b", text, re.IGNORECASE) or
        re.search(r"\bwe further order\b", text, re.IGNORECASE) or
        re.search(r"\bare directed to\b", text, re.IGNORECASE) or
        re.search(r"\bare required to provide\b", text, re.IGNORECASE) or
        re.search(r"\bshall be\b", text, re.IGNORECASE) or
        re.search(r"\bis directed to\b", text, re.IGNORECASE)):
        return "Yes"
    return "No"