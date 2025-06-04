import os
import time
import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from twocaptcha import TwoCaptcha
from PIL import Image
from sqlalchemy import create_engine, Table, Column, String, MetaData, insert
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import sessionmaker

metadata = MetaData()

ecourts_table = Table("ecourts_supreme_courts", metadata,
    Column("cnr_number", String, primary_key=True),
    Column("title", String),
    Column("diary_number", String),
    Column("case_number", String),
    Column("present_last_listed_on", String),
    Column("status_stage", String),
    Column("admitted", String),
    Column("category", String),
    Column("petitioner", String),
    Column("respondent", String),
    Column("petitioner_advocate", String),
    Column("respondent_advocate", String),
    schema="public"
)

# Update with your actual DB credentials
DATABASE_URL = "postgresql+psycopg2://postgres:1951@localhost/postgres"

engine = create_engine(DATABASE_URL)
metadata = MetaData()
Session = sessionmaker(bind=engine)
session = Session()

def extract_case_details(driver, cnr_number):
    soup = BeautifulSoup(driver.page_source, "html.parser")

    # Header content
    header_div = soup.find("div", id="cnrResultsDetails")
    heading_text = ""
    if header_div:
        h3 = header_div.find("h3")
        h4 = header_div.find("h4")
        heading_text = ""
        if h3: heading_text += h3.get_text(strip=True) + "\n"
        if h4: heading_text += h4.get_text(strip=True) + "\n"

    # Table data
    tbody = soup.find("tbody", attrs={"data-fetched": "true"})
    data = {}
    if tbody:
        for row in tbody.find_all("tr"):
            cols = row.find_all("td")
            if len(cols) == 2:
                key = cols[0].get_text(strip=True).replace("\xa0", " ").strip()
                value_html = cols[1]
                for br in value_html.find_all("br"):
                    br.replace_with("\n")
                value = value_html.get_text(separator=' ', strip=True)
                data[key] = value
                print(f"[Parsed] {key}: {value}")

    # Prepare folder
    folder_name = cnr_number.replace("/", "_")
    os.makedirs(folder_name, exist_ok=True)
    file_path = os.path.join(folder_name, f"{folder_name}.txt")

    # Write to TXT
    with open(file_path, "w", encoding="utf-8") as f:
        if heading_text:
            f.write(heading_text.strip() + "\n\n")

        for key in [
            "Diary Number", "Case Number", "CNR Number", "Present/Last Listed On", "Status/Stage",
            "Admitted", "Category", "Petitioner(s)", "Respondent(s)",
            "Petitioner Advocate(s)", "Respondent Advocate(s)"
        ]:
            if key in data:
                f.write(f"{key}:\n{data[key]}\n\n")

    print(f"✅ Selective case data saved to: {file_path}")

    # Insert into PostgreSQL
    try:
        row_data = {
            "cnr_number": data.get("CNR Number", cnr_number),
            "title": heading_text.strip(),
            "diary_number": data.get("Diary Number", ""),
            "case_number": data.get("Case Number", ""),
            "present_last_listed_on": data.get("Present/Last Listed On", ""),
            "status_stage": data.get("Status/Stage", ""),
            "admitted": data.get("Admitted", ""),
            "category": data.get("Category", ""),
            "petitioner": data.get("Petitioner(s)", ""),
            "respondent": data.get("Respondent(s)", ""),
            "petitioner_advocate": data.get("Petitioner Advocate(s)", ""),
            "respondent_advocate": data.get("Respondent Advocate(s)", "")
        }

        stmt = insert(ecourts_table).values(**row_data).on_conflict_do_nothing(index_elements=["cnr_number"])
        session.execute(stmt)
        session.commit()
        print("🗃️ Case data inserted into PostgreSQL.")
    except Exception as e:
        print(f"❌ Failed to insert into PostgreSQL: {e}")


    # Optional: Insert into PostgreSQL
    try:
        with engine.connect() as conn:
            stmt = insert(ecourts_table).values(
                cnr_number=data.get("CNR Number", cnr_number),
                title=heading_text.strip(),
                diary_number=data.get("Diary Number", ""),
                case_number=data.get("Case Number", ""),
                present_last_listed_on=data.get("Present/Last Listed On", ""),
                status_stage=data.get("Status/Stage", ""),
                admitted=data.get("Admitted", ""),
                category=data.get("Category", ""),
                petitioner=data.get("Petitioner(s)", ""),
                respondent=data.get("Respondent(s)", ""),
                petitioner_advocate=data.get("Petitioner Advocate(s)", ""),
                respondent_advocate=data.get("Respondent Advocate(s)", "")
            ).on_conflict_do_nothing(index_elements=["cnr_number"])
            conn.execute(stmt)
            print("🗃️ Case data inserted into PostgreSQL.")
    except Exception as e:
        print(f"❌ Failed to insert into PostgreSQL: {e}")


# Input from user
cnr_number = input("Enter the CNR Number: ")

# Launch visible Chrome browser
driver = webdriver.Chrome()
driver.maximize_window()
driver.get("https://www.sci.gov.in/case-status-cnr-number/")

# Fill in the CNR Number
cnr_input = WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.ID, "cnr_no"))
)
cnr_input.send_keys(cnr_number)
time.sleep(3)  # ⏱️ Wait for 3 seconds after entering CNR


# Wait for CAPTCHA image to load
WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.ID, "siwp_captcha_value_0"))
)

# Initialize 2Captcha solver with your API key
solver = TwoCaptcha('6e8f5fdfb967c46f1589fb420d52579f')

# Wait for CAPTCHA image to load
captcha_element = WebDriverWait(driver, 20).until(
    EC.presence_of_element_located((By.ID, "siwp_captcha_value_0"))
)

# Screenshot CAPTCHA image
captcha_img = driver.find_element(By.ID, "siwp_captcha_image_0")
captcha_img_path = 'supreme_captcha.png'
captcha_img.screenshot(captcha_img_path)
print("🖼 CAPTCHA image saved. Sending to 2Captcha...")

# Solve via 2Captcha
try:
    result = solver.normal(file=captcha_img_path)
    raw_code = result['code'].strip()
    print(f"✅ CAPTCHA solved by 2Captcha: {raw_code}")

    # Evaluate if it's a math expression like "4+4"
    try:
        captcha_input = str(eval(raw_code))
        print(f"🧮 Evaluated CAPTCHA: {captcha_input}")
    except:
        captcha_input = raw_code  # fallback if not evaluable
        print(f"⚠️ Could not evaluate, using as-is: {captcha_input}")
except Exception as e:
    print(f"❌ Failed to solve CAPTCHA: {e}")
    driver.quit()
    exit()


# Enter CAPTCHA into the form
driver.find_element(By.ID, "siwp_captcha_value_0").send_keys(captcha_input)


# Locate the "Search" submit button reliably
search_btn = WebDriverWait(driver, 10).until(
    EC.element_to_be_clickable((By.XPATH, "//input[@type='submit' and @value='Search']"))
)
search_btn.click()


# Wait for results and attempt to click "View"
try:
    print("🔎 Waiting for 'View' button to appear...")
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.LINK_TEXT, "View"))
    )
    view_btn = driver.find_element(By.LINK_TEXT, "View")
    print("✅ 'View' button found, clicking...")
    view_btn.click()
    print("⏳ Waiting for case detail page to load...")
    WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.ID, "cnrResultsDetails"))
    )
    print("✅ Case detail page loaded.")

except Exception as e:
    print("❌ Failed to find or click the 'View' button.")
    driver.save_screenshot("view_button_debug.png")
    print("📸 Screenshot saved: view_button_debug.png")
    print("🧩 Error detail:", e)
    driver.quit()
    exit()


# Wait for case detail page to load
WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
time.sleep(2)

# Create folder based on CNR
folder_name = cnr_number.replace("/", "_")
os.makedirs(folder_name, exist_ok=True)

# Save page text
extract_case_details(driver, cnr_number)

pdf_links = []

try:
    print("Locating Judgement/Orders expand button...")
    # Step 1: Find the expand button
    expand_button = WebDriverWait(driver, 15).until(
        EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'judgement_orders')]//button[contains(text(), 'Judgement/Orders')]"))
    )

    # Step 2: Scroll to it
    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", expand_button)
    time.sleep(1)

    # Step 3: Click the button to expand
    expand_button.click()
    time.sleep(1.5)

    # Step 4: Wait for <tbody> to become visible (i.e., not hidden anymore)
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//table[contains(@class, 'judgement_orders')]//tbody[not(contains(@class, 'hide'))]"))
    )

    print("Judgement/Orders section is now visible.")

    # Step 5: Find all PDF links in this specific table
    pdf_links = driver.find_elements(By.XPATH, "//table[contains(@class, 'judgement_orders')]//tbody[not(contains(@class, 'hide'))]//a[contains(@href, '.pdf')]")

    print(f"Found {len(pdf_links)} PDF(s) in Judgement/Orders section.")

    # Step 6: Download PDFs
    if not pdf_links:
        print("⚠️ No PDF links found.")
    else:
        os.makedirs(folder_name, exist_ok=True)
        for link in pdf_links:
            url = link.get_attribute("href")
            filename = os.path.join(folder_name, os.path.basename(url))
            try:
                r = requests.get(url)
                with open(filename, "wb") as f:
                    f.write(r.content)
                print(f"⬇️ Downloaded: {filename}")
            except Exception as e:
                print(f"⚠️ Error downloading {url}: {e}")

except Exception as e:
    print(f"❌ Error expanding or processing Judgement/Orders section: {e}")

for link in pdf_links:
    pdf_url = link.get_attribute("href")
    file_path = os.path.join(folder_name, os.path.basename(pdf_url))
    try:
        r = requests.get(pdf_url)
        with open(file_path, "wb") as f:
            f.write(r.content)
        print(f"⬇️ PDF downloaded: {file_path}")
    except:
        print(f"⚠️ Failed to download PDF: {pdf_url}")

driver.quit()
