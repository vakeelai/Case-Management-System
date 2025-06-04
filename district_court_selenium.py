#!/usr/bin/env python3
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import traceback
import os
import pandas as pd
import requests
from urllib.parse import urljoin
from selenium.webdriver.common.keys import Keys

def extract_case_details(driver):
    """
    Extract case details from the results page
    """
    print("Extracting case details...")
    case_data = {}
    
    try:
        # Take a screenshot of results for reference
        driver.save_screenshot("case_details.png")
        print("Saved case details screenshot")
        
        # Extract case details from the page
        # Case Details section
        try:
            case_details_tables = driver.find_elements(By.CSS_SELECTOR, "table.case_details_table")
            if case_details_tables:
                print(f"Found {len(case_details_tables)} case details tables")
                
                # Process first table (Case Details)
                rows = case_details_tables[0].find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        label_cell = cells[0]
                        
                        # Use JavaScript to get the text content of the direct text nodes in the cell
                        js_script = """
                            var parent = arguments[0];
                            var text = '';
                            for (var i = 0; i < parent.childNodes.length; i++) {
                                var node = parent.childNodes[i];
                                if (node.nodeType === Node.TEXT_NODE && node.textContent.trim() !== '') {
                                    text = node.textContent.trim();
                                    break;
                                }
                            }
                            return text;
                        """
                        key = driver.execute_script(js_script, label_cell)

                        # If JavaScript didn't find a text node, try the previous label/textContent logic as fallback
                        if not key:
                             # Get the text content of the cell first as fallback
                            key = label_cell.get_attribute('textContent').strip()
                            
                            # If there is a non-empty label, use its text as the key as a secondary fallback
                            labels = label_cell.find_elements(By.TAG_NAME, "label")
                            if labels:
                                label_text = labels[0].text.strip()
                                if label_text:
                                    key = label_text
                            
                        # Clean up potential extra whitespace/newlines in the key
                        key = ' '.join(key.split())

                        if key and len(cells) > 1:
                            value = cells[1].text.strip()
                            case_data[key] = value
                            print(f"Extracted: {key} = {value}")
        except Exception as e:
            print(f"Error extracting case details: {e}")
        
        # Case Status section
        try:
            case_status_tables = driver.find_elements(By.CSS_SELECTOR, "table.case_status_table")
            if case_status_tables:
                print(f"Found {len(case_status_tables)} case status tables")
                
                # Process case status table
                status_data = {}
                rows = case_status_tables[0].find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        label_cell = cells[0]
                        labels = label_cell.find_elements(By.TAG_NAME, "label")
                        if labels:
                            key = labels[0].text.strip()
                        else:
                            key = label_cell.text.strip()
                            
                        if key and len(cells) > 1:
                            value = cells[1].text.strip()
                            status_data[key] = value
                            print(f"Extracted status: {key} = {value}")
                
                # Add status data to main data dictionary with "Status_" prefix
                for key, value in status_data.items():
                    case_data[f"Status_{key}"] = value
        except Exception as e:
            print(f"Error extracting case status: {e}")
        
        # Petitioner and Advocate section
        try:
            petitioner_advocate_tables = driver.find_elements(By.CSS_SELECTOR, "table.Petitioner_Advocate_table")
            if petitioner_advocate_tables:
                print(f"Found {len(petitioner_advocate_tables)} Petitioner and Advocate tables")
                
                # Process Petitioner and Advocate table
                petitioner_advocate_entries = []
                rows = petitioner_advocate_tables[0].find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        # Extract text and split by lines (handling <br> tags)
                        html_content = driver.execute_script("return arguments[0].innerHTML;", cells[0])
                        entries = [entry.strip() for entry in html_content.split('<br>') if entry.strip()]
                        petitioner_advocate_entries.extend(entries)
                        print(f"Extracted Petitioner/Advocate entries: {entries}")
                
                # Add data to main data dictionary
                for i, entry in enumerate(petitioner_advocate_entries):
                    case_data[f"Petitioner_Advocate_{i+1}"] = entry

        except Exception as e:
            print(f"Error extracting Petitioner and Advocate details: {e}")

        # Respondent and Advocate section
        try:
            respondent_advocate_tables = driver.find_elements(By.CSS_SELECTOR, "table.Respondent_Advocate_table")
            if respondent_advocate_tables:
                print(f"Found {len(respondent_advocate_tables)} Respondent and Advocate tables")
                
                # Process Respondent and Advocate table
                respondent_advocate_entries = []
                rows = respondent_advocate_tables[0].find_elements(By.TAG_NAME, "tr")
                for row in rows:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                         # Extract text and split by lines (handling <br> tags)
                        html_content = driver.execute_script("return arguments[0].innerHTML;", cells[0])
                        entries = [entry.strip() for entry in html_content.split('<br>') if entry.strip()]
                        respondent_advocate_entries.extend(entries)
                        print(f"Extracted Respondent/Advocate entries: {entries}")

                # Add data to main data dictionary
                for i, entry in enumerate(respondent_advocate_entries):
                    case_data[f"Respondent_Advocate_{i+1}"] = entry

        except Exception as e:
            print(f"Error extracting Respondent and Advocate details: {e}")

        # Acts section
        try:
            acts_tables = driver.find_elements(By.CSS_SELECTOR, "table.acts_table")
            if acts_tables:
                print(f"Found {len(acts_tables)} Acts tables")
                
                # Process Acts table (skip header row)
                acts_data = {}
                rows = acts_tables[0].find_elements(By.TAG_NAME, "tr")
                for i, row in enumerate(rows):
                    # Skip header row (assuming the first row contains <th>)
                    if row.find_elements(By.TAG_NAME, 'th'):
                        continue

                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 2:
                        act = cells[0].text.strip()
                        section = cells[1].text.strip()
                        if act or section:
                            acts_data[f"Acts_Act_{len(acts_data) // 2 + 1}"] = act
                            acts_data[f"Acts_Section_{len(acts_data) // 2 + 1}"] = section
                            print(f"Extracted Act: {act}, Section: {section}")

                # Add data to main data dictionary
                case_data.update(acts_data)

        except Exception as e:
            print(f"Error extracting Acts details: {e}")
        
        # --- Modal Data Extraction ---
        try:
            print("Looking for modal trigger link...")
            # Find the link that triggers the modal (based on screenshot/onclick)
            modal_link = driver.find_element(By.XPATH, "//a[contains(@onclick, 'display_case_acknowledgement')]" )# or By.PARTIAL_LINK_TEXT, 'View CNR Code' based on text
            
            if modal_link:
                print("Found modal trigger link. Clicking...")
                modal_link.click()
                
                # Wait for the modal to appear and content to load
                # Wait for the modal body with id 'modal_ack_body' to be visible
                wait = WebDriverWait(driver, 10)
                modal_body = wait.until(EC.visibility_of_element_located((By.ID, "modal_ack_body")))
                print("Modal is visible. Extracting data...")
                
                modal_data = {}
                # Extract data from the table within the modal body
                modal_tables = modal_body.find_elements(By.TAG_NAME, "table")
                if modal_tables:
                    modal_rows = modal_tables[0].find_elements(By.TAG_NAME, "tr")
                    for row in modal_rows:
                        cells = row.find_elements(By.TAG_NAME, "td")
                        # Assuming a structure of Label | : | Value
                        if len(cells) >= 3:
                            label = cells[0].text.strip()
                            value = cells[2].text.strip()
                            if label:
                                modal_data[f"Modal_{label}"] = value
                                print(f"Extracted Modal Data: {label} = {value}")
                
                # Add modal data to the main case data
                case_data.update(modal_data)
                print("Modal data extracted and added.")
                
                # Close the modal (look for a close button or use Escape key/JS)
                # Assuming a close button with class 'close' or similar in the modal header
                try:
                    close_button = driver.find_element(By.CSS_SELECTOR, ".modal-header .close") # Common class for modal close button
                    print("Found modal close button. Clicking...")
                    close_button.click()
                    print("Modal closed.")
                except Exception as close_e:
                    print(f"Could not find a common modal close button: {close_e}. Trying Escape key...")
                    # Alternatively, try sending ESC key to close modal
                    from selenium.webdriver.common.keys import Keys
                    driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                    print("Sent Escape key.")
                    # Give a moment for modal to close
                    time.sleep(1)

            else:
                print("Modal trigger link not found.")
                
        except Exception as e:
            print(f"Error extracting modal data: {e}")
            traceback.print_exc()
        # --- End Modal Data Extraction ---
        
        # Look for PDF links
        pdf_links = []
        try:
            links = driver.find_elements(By.TAG_NAME, "a")
            for link in links:
                href = link.get_attribute("href")
                if href and ("display_pdf" in href or ".pdf" in href):
                    pdf_links.append(href)
                    print(f"Found PDF link: {href}")
            
            case_data["pdf_links"] = pdf_links
        except Exception as e:
            print(f"Error extracting PDF links: {e}")
            
        return case_data
    except Exception as e:
        print(f"Error in extract_case_details: {e}")
        traceback.print_exc()
        return {}

def extract_order_pdfs(driver, folder_path):
    """
    Extract and download PDFs from the order table
    """
    try:
        print("Looking for order table...")
        # Find the order table - it has class "order_table table"
        order_table = driver.find_element(By.CSS_SELECTOR, "table.order_table.table")
        
        if order_table:
            print("Found order table")
            # Find all rows in tbody
            rows = order_table.find_elements(By.TAG_NAME, "tr")
            
            for row_index, row in enumerate(rows):
                try:
                    # Find cells
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if len(cells) >= 3:  # We expect at least 3 columns
                        # The third column contains the PDF link
                        pdf_cell = cells[2]
                        pdf_link = pdf_cell.find_element(By.TAG_NAME, "a")
                        
                        if pdf_link:
                            # Get the onclick attribute
                            onclick_attr = pdf_link.get_attribute("onclick")
                            if onclick_attr and "displayPdf" in onclick_attr:
                                print(f"Found PDF link in row {row_index + 1}")
                                
                                # Extract the URL parameters from onclick attribute
                                params_start = onclick_attr.find("('") + 2
                                params_end = onclick_attr.find("')")
                                if params_start > 1 and params_end > params_start:
                                    params = onclick_attr[params_start:params_end]
                                    
                                    # Construct the PDF URL
                                    base_url = "https://services.ecourts.gov.in/ecourtindia_v6/"
                                    pdf_url = f"{base_url}{params}"
                                    
                                    try:
                                        # Get cookies from the driver
                                        cookies = driver.get_cookies()
                                        cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
                                        
                                        # Make request with cookies
                                        print(f"Downloading PDF from {pdf_url}")
                                        response = requests.get(pdf_url, cookies=cookies_dict, stream=True)
                                        
                                        if response.status_code == 200:
                                            # Create a filename using the date from the row
                                            date_cell = cells[1]
                                            date_text = date_cell.text.strip().replace("/", "-")
                                            filename = f"order_{date_text}.pdf"
                                            file_path = os.path.join(folder_path, filename)
                                            
                                            # Save the PDF
                                            with open(file_path, 'wb') as pdf_file:
                                                for chunk in response.iter_content(chunk_size=1024):
                                                    if chunk:
                                                        pdf_file.write(chunk)
                                            
                                            print(f"Successfully downloaded PDF to {file_path}")
                                        else:
                                            print(f"Failed to download PDF. Status code: {response.status_code}")
                                            
                                    except Exception as download_e:
                                        print(f"Error downloading PDF: {download_e}")
                                        traceback.print_exc()
                                        
                except Exception as row_e:
                    print(f"Error processing row {row_index + 1}: {row_e}")
                    continue
            
    except Exception as e:
        print(f"Error extracting order PDFs: {e}")
        traceback.print_exc()

def create_case_folder(cnr_number, case_data):
    """
    Create a folder named after the CNR number and save case data to Excel
    """
    print(f"Creating folder for CNR: {cnr_number}")
    
    # Create folder if it doesn't exist
    folder_name = cnr_number.replace("/", "_").replace("\\", "_").strip()
    if not folder_name:
        folder_name = "unknown_cnr"
    
    os.makedirs(folder_name, exist_ok=True)
    print(f"Created folder: {folder_name}")
    
    # Create Excel file with case data
    if case_data:
        try:
            # Convert dictionary to DataFrame
            # Remove any PDF links first as they won't display well in Excel
            pdf_links = case_data.pop("pdf_links", [])
            
            # Create DataFrame from remaining data
            df = pd.DataFrame([case_data])
            
            # Save to Excel
            excel_path = os.path.join(folder_name, f"{folder_name}_case_details.xlsx")
            df.to_excel(excel_path, index=False)
            print(f"Saved case details to Excel: {excel_path}")
            
            # Return the folder path for PDF downloads
            return folder_name
        except Exception as e:
            print(f"Error saving Excel file: {e}")
            traceback.print_exc()
    
    return folder_name

def download_pdfs(driver, pdf_links, folder_path):
    """
    Download PDF files from the provided links
    """
    print(f"Downloading {len(pdf_links)} PDF files...")
    
    downloaded = 0
    for i, pdf_url in enumerate(pdf_links):
        try:
            print(f"Downloading PDF {i+1}/{len(pdf_links)}: {pdf_url}")
            
            # Get cookies from the driver
            cookies = driver.get_cookies()
            cookies_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            # Ensure the URL is absolute
            if not pdf_url.startswith(('http://', 'https://')):
                pdf_url = urljoin(driver.current_url, pdf_url)
            
            # Make request with cookies and download the file
            response = requests.get(pdf_url, cookies=cookies_dict, stream=True)
            
            if response.status_code == 200:
                # Extract filename from URL or use a default name
                filename = pdf_url.split('/')[-1]
                if not filename or not filename.endswith('.pdf'):
                    filename = f"document_{i+1}.pdf"
                
                # Save PDF to the folder
                file_path = os.path.join(folder_path, filename)
                with open(file_path, 'wb') as file:
                    for chunk in response.iter_content(chunk_size=1024):
                        if chunk:
                            file.write(chunk)
                
                print(f"Downloaded PDF to {file_path}")
                downloaded += 1
            else:
                print(f"Failed to download PDF. Status code: {response.status_code}")
        
        except Exception as e:
            print(f"Error downloading PDF: {e}")
            traceback.print_exc()
    
    print(f"Downloaded {downloaded}/{len(pdf_links)} PDF files")
    return downloaded

def extract_business_details(driver, folder_path):
    """
    Extract business details from the case history popup/page
    """
    try:
        print("\nLooking for case history business link...")
        # Find all links with viewBusiness in onclick
        business_links = driver.find_elements(By.CSS_SELECTOR, "a[onclick*='viewBusiness']")
        
        if business_links:
            # Get the last link as it contains the most recent history
            last_link = business_links[-1]
            print("Found business history link")
            
            # Extract date and other parameters from onclick
            onclick = last_link.get_attribute("onclick")
            if onclick:
                # Get the parameters from viewBusiness function call
                params_start = onclick.find("(") + 1
                params_end = onclick.find(")")
                if params_start > 0 and params_end > params_start:
                    params = onclick[params_start:params_end].replace("'", "").split(",")
                    date = params[6] if len(params) > 6 else "unknown_date"
                    print(f"Business details date: {date}")
                    
                    # Store main window handle
                    main_window = driver.current_window_handle
                    
                    # Scroll to and click the link
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", last_link)
                    time.sleep(1)
                    last_link.click()
                    time.sleep(2)
                    
                    try:
                        # Wait for the business details div to load
                        wait = WebDriverWait(driver, 10)
                        business_div = wait.until(EC.presence_of_element_located((By.ID, "caseBusinessDiv_cnr")))
                        
                        if business_div:
                            print("Found business details div")
                            
                            # Create history folder
                            history_folder = os.path.join(folder_path, "history")
                            os.makedirs(history_folder, exist_ok=True)
                            
                            # Extract all text content
                            content = []
                            
                            # Add Daily Status header
                            daily_status = business_div.find_element(By.XPATH, ".//span[contains(., 'Daily Status')]")
                            if daily_status:
                                content.append("Daily Status")
                                content.append("-" * 50)  # Add separator line
                            
                            # Extract court details
                            court_details = business_div.find_elements(By.TAG_NAME, "center")
                            for detail in court_details:
                                text = detail.text.strip()
                                if text:
                                    content.append(text)
                            
                            # Extract table data
                            table = business_div.find_element(By.CSS_SELECTOR, "table[width='87%']")
                            if table:
                                rows = table.find_elements(By.TAG_NAME, "tr")
                                for row in rows:
                                    cells = row.find_elements(By.TAG_NAME, "td")
                                    if len(cells) >= 3:  # We expect 3 columns
                                        # Get the label (first column)
                                        label = cells[0].text.strip()
                                        if label:
                                            # Get the value (third column)
                                            value = cells[2].text.strip()
                                            if value:
                                                content.append(f"{label}: {value}")
                            
                            # Save to file
                            filename = f"business_details_{date.replace('/', '-')}.txt"
                            file_path = os.path.join(history_folder, filename)
                            
                            with open(file_path, 'w', encoding='utf-8') as f:
                                f.write("\n".join(content))
                            
                            print(f"✅ Saved business details to: {file_path}")
                            
                            # Try multiple methods to close the modal/popup
                            print("Attempting to close modal...")
                            close_success = False
                            
                            # Method 1: Try clicking close button with wait
                            try:
                                wait = WebDriverWait(driver, 5)
                                close_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, 
                                    "button.btn-close[data-bs-dismiss='modal'], .modal-header .close")))
                                close_button.click()
                                time.sleep(1)
                                close_success = True
                                print("Closed modal using close button")
                            except Exception as e:
                                print(f"Method 1 failed: {e}")
                            
                            # Method 2: Try JavaScript click on close button
                            if not close_success:
                                try:
                                    driver.execute_script("""
                                        var closeButtons = document.querySelectorAll('button.btn-close[data-bs-dismiss="modal"], .modal-header .close');
                                        if (closeButtons.length > 0) closeButtons[0].click();
                                    """)
                                    time.sleep(1)
                                    close_success = True
                                    print("Closed modal using JavaScript click")
                                except Exception as e:
                                    print(f"Method 2 failed: {e}")
                            
                            # Method 3: Try to hide modal using JavaScript
                            if not close_success:
                                try:
                                    driver.execute_script("""
                                        var modals = document.querySelectorAll('.modal.show');
                                        modals.forEach(function(modal) {
                                            modal.style.display = 'none';
                                            modal.classList.remove('show');
                                        });
                                        var backdrops = document.querySelectorAll('.modal-backdrop');
                                        backdrops.forEach(function(backdrop) {
                                            backdrop.remove();
                                        });
                                        document.body.classList.remove('modal-open');
                                        document.body.style.overflow = '';
                                        document.body.style.paddingRight = '';
                                    """)
                                    time.sleep(1)
                                    close_success = True
                                    print("Closed modal using JavaScript hide")
                                except Exception as e:
                                    print(f"Method 3 failed: {e}")
                            
                            # Method 4: Try Escape key as last resort
                            if not close_success:
                                try:
                                    actions = webdriver.ActionChains(driver)
                                    actions.send_keys(Keys.ESCAPE).perform()
                                    time.sleep(1)
                                    print("Sent Escape key to close modal")
                                except Exception as e:
                                    print(f"Method 4 failed: {e}")
                            
                            return True
                            
                    except Exception as e:
                        print(f"Error extracting business details: {e}")
                        traceback.print_exc()
                        
                        # Ensure we're back on main window
                        if len(driver.window_handles) > 1:
                            driver.close()
                            driver.switch_to.window(main_window)
        else:
            print("No business history links found")
            
    except Exception as e:
        print(f"Error in extract_business_details: {e}")
        traceback.print_exc()
    
    return False

def main():
    """
    Use Selenium to navigate to the eCourts website, click on the High Courts Services button,
    and then allow manual entry of CNR number and CAPTCHA before clicking search.
    """
    print("Starting eCourts navigation with Selenium...")
    
    # Create a browser instance
    driver = None
    try:
        # Set up Chrome options
        print("Setting up Chrome options...")
        options = Options()
        options.add_argument("--start-maximized")  # Start maximized
        options.add_argument("--disable-notifications")  # Disable notifications
        
        # Initialize the Chrome driver
        print("Initializing Chrome driver...")
        driver = webdriver.Chrome(options=options)
        
        # Create a wait object for waiting for elements
        wait = WebDriverWait(driver, 20)  # Wait up to 20 seconds
        
        # Navigate to the eCourts homepage
        print("Navigating to eCourts homepage...")
        driver.get("https://ecourts.gov.in/ecourts_home/")
        
        # Wait for the page to load
        time.sleep(3)
        
        # Print page title for confirmation
        print(f"Page title: {driver.title}")
        
        # Try different strategies to find the District Court Services button
        print("Looking for District Court Services button...")
        button = None
        
        # Strategy 1: Find by href and title
        try:
            print("Strategy 1: Find by href and title...")
            button = driver.find_element(By.CSS_SELECTOR, 'a[href="https://services.ecourts.gov.in"][title="District Court Services"]')
            print("Found button by href and title")
        except Exception as e:
            print(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Find by href only
        if button is None:
            try:
                print("Strategy 2: Find by href only...")
                button = driver.find_element(By.CSS_SELECTOR, 'a[href="https://services.ecourts.gov.in"]')
                print("Found button by href")
            except Exception as e:
                print(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Find by title only
        if button is None:
            try:
                print("Strategy 3: Find by title only...")
                button = driver.find_element(By.CSS_SELECTOR, 'a[title="District Court Services"]')
                print("Found button by title")
            except Exception as e:
                print(f"Strategy 3 failed: {e}")
        
        # Strategy 4: Find by link text
        if button is None:
            try:
                print("Strategy 4: Find by link text...")
                button = driver.find_element(By.LINK_TEXT, "District Court Services")
                print("Found button by link text")
            except Exception as e:
                print(f"Strategy 4 failed: {e}")
                
        # Strategy 5: Find by partial link text
        if button is None:
            try:
                print("Strategy 5: Find by partial link text...")
                button = driver.find_element(By.PARTIAL_LINK_TEXT, "District Court")
                print("Found button by partial link text")
            except Exception as e:
                print(f"Strategy 5 failed: {e}")
                
        # Strategy 6: Find by XPath containing text
        if button is None:
            try:
                print("Strategy 6: Find by XPath...")
                button = driver.find_element(By.XPATH, "//a[contains(text(), 'District Court Services')]")
                print("Found button by XPath")
            except Exception as e:
                print(f"Strategy 6 failed: {e}")
                
        # Strategy 7: Find by class and tabindex (from the screenshot)
        if button is None:
            try:
                print("Strategy 7: Find by class and tabindex...")
                button = driver.find_element(By.CSS_SELECTOR, "a.btn.btn-default[tabindex='0']")
                print("Found button by class and tabindex")
            except Exception as e:
                print(f"Strategy 7 failed: {e}")
                
        # If button is found, take a screenshot, scroll to it, and click it
        if button:
            # Take a screenshot before clicking
            print("Taking screenshot before clicking...")
            driver.save_screenshot("before_click.png")
            
            # Scroll to the button
            print("Scrolling to button...")
            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", button)
            time.sleep(2)
            
            # Highlight the button for visibility
            print("Highlighting button...")
            driver.execute_script("arguments[0].style.border='3px solid red';", button)
            time.sleep(1)
            
            # Click the button
            print("Clicking button...")
            button.click()
            
            # Wait for navigation
            time.sleep(5)
            
            # Take a screenshot after clicking
            print("Taking screenshot after clicking...")
            driver.save_screenshot("after_click.png")
            
            # Print the current URL
            print(f"Current URL after click: {driver.current_url}")
            
            print("Successfully clicked on District Court Services button!")
            
            # Now find and interact with the CNR number input field
            try:
                print("Looking for CNR number input field...")
                cnr_input = None
                
                # Try multiple strategies to find the CNR input
                try:
                    cnr_input = driver.find_element(By.ID, "cino")
                    print("Found CNR input by ID")
                except Exception:
                    try:
                        cnr_input = driver.find_element(By.NAME, "cino")
                        print("Found CNR input by name")
                    except Exception:
                        try:
                            cnr_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='Enter 16 digit CNR number']")
                            print("Found CNR input by placeholder")
                        except Exception:
                            print("Could not find CNR input with standard selectors")
                
                if cnr_input:
                    # Focus on the CNR input field
                    driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", cnr_input)
                    time.sleep(1)
                    
                    # Highlight the CNR input field
                    driver.execute_script("arguments[0].style.border='3px solid blue';", cnr_input)
                    
                    # Ask for CNR number
                    cnr_number = input("Please enter the 16-digit CNR number: ")
                    
                    # Input the CNR number
                    cnr_input.clear()
                    cnr_input.send_keys(cnr_number)
                    print(f"Entered CNR number: {cnr_number}")
                    
                    # Take a screenshot of the whole page to see CAPTCHA
                    print("Taking screenshot to show CAPTCHA...")
                    driver.save_screenshot("captcha_page.png")
                    print("Screenshot saved as 'captcha_page.png' - check this file to see the CAPTCHA")
                    
                    # Now find the CAPTCHA input field - use multiple strategies
                    print("Looking for CAPTCHA input field...")
                    captcha_input = None
                    
                    # Strategy 1: By ID
                    try:
                        captcha_input = driver.find_element(By.ID, "fcaptcha_code")
                        print("Found CAPTCHA input by ID")
                    except Exception as e:
                        print(f"Could not find CAPTCHA by ID: {e}")
                        
                    # Strategy 2: By name
                    if captcha_input is None:
                        try:
                            captcha_input = driver.find_element(By.NAME, "fcaptcha_code")
                            print("Found CAPTCHA input by name")
                        except Exception as e:
                            print(f"Could not find CAPTCHA by name: {e}")
                            
                    # Strategy 3: By class
                    if captcha_input is None:
                        try:
                            captcha_input = driver.find_element(By.CSS_SELECTOR, "input.form-control.w-125")
                            print("Found CAPTCHA input by class")
                        except Exception as e:
                            print(f"Could not find CAPTCHA by class: {e}")
                            
                    # Strategy 4: By placeholder
                    if captcha_input is None:
                        try:
                            captcha_input = driver.find_element(By.CSS_SELECTOR, "input[placeholder='Enter Captcha']")
                            print("Found CAPTCHA input by placeholder")
                        except Exception as e:
                            print(f"Could not find CAPTCHA by placeholder: {e}")
                            
                    # Strategy 5: By XPath
                    if captcha_input is None:
                        try:
                            captcha_input = driver.find_element(By.XPATH, "//input[@type='text' and @maxlength='6']")
                            print("Found CAPTCHA input by xpath type and maxlength")
                        except Exception as e:
                            print(f"Could not find CAPTCHA by xpath: {e}")
                            
                    # If CAPTCHA input is found, interact with it
                    if captcha_input:
                        # Focus on the CAPTCHA input field
                        driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", captcha_input)
                        time.sleep(1)
                        
                        # Highlight the CAPTCHA input field
                        driver.execute_script("arguments[0].style.border='3px solid green';", captcha_input)
                        
                        # Take a screenshot of the captcha area
                        driver.save_screenshot("captcha_highlighted.png")
                        
                        # Ask user to enter the CAPTCHA
                        print("\n*** CAPTCHA ENTRY REQUIRED ***")
                        print("A screenshot has been saved as 'captcha_highlighted.png' for reference.")
                        print("Please look at the browser window and enter the CAPTCHA code shown.")
                        captcha_value = input("Enter CAPTCHA value: ")
                        
                        # Input the CAPTCHA value
                        captcha_input.clear()
                        captcha_input.send_keys(captcha_value)
                        print("Entered CAPTCHA value")
                        
                        # Now find and click the search button using multiple strategies
                        print("Looking for search button...")
                        search_button = None
                        
                        # Strategy 1: By ID
                        try:
                            search_button = driver.find_element(By.ID, "searchbtn")
                            print("Found search button by ID")
                        except Exception:
                            print("Could not find search button by ID")
                            
                        # Strategy 2: By type and value
                        if search_button is None:
                            try:
                                search_button = driver.find_element(By.CSS_SELECTOR, "button[type='button'][onclick='funViewCinoHistory();']")
                                print("Found search button by type and onclick")
                            except Exception:
                                print("Could not find search button by type and onclick")
                                
                        # Strategy 3: By XPath with text
                        if search_button is None:
                            try:
                                search_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Search')]")
                                print("Found search button by text")
                            except Exception:
                                print("Could not find search button by text")
                                
                        # Strategy 4: By class
                        if search_button is None:
                            try:
                                search_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary")
                                print("Found search button by class")
                            except Exception:
                                print("Could not find search button by class")
                        
                        # If search button is found, click it
                        if search_button:
                            # Focus on the search button
                            driver.execute_script("arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});", search_button)
                            time.sleep(1)
                            
                            # Highlight the search button
                            driver.execute_script("arguments[0].style.border='3px solid red';", search_button)
                            time.sleep(1)
                            
                            # Click the search button
                            print("Clicking search button...")
                            search_button.click()
                            
                            # Wait for search results
                            print("Waiting for search results...")
                            time.sleep(5)
                            
                            # Take a screenshot of the results
                            driver.save_screenshot("search_results.png")
                            print("Search results screenshot saved as 'search_results.png'")
                            
                            # Now extract the case details
                            case_data = extract_case_details(driver)
                            
                            if case_data:
                                print("Successfully extracted case details")
                                
                                # Create folder and Excel file
                                folder_path = create_case_folder(cnr_number, case_data)
                                
                                # Download PDF files if available
                                if case_data.get("pdf_links", []):
                                    download_pdfs(driver, case_data["pdf_links"], folder_path)
                                else:
                                    print("No PDF links found to download")
                                
                                # Extract and download order PDFs
                                print("\nAttempting to download order PDFs...")
                                extract_order_pdfs(driver, folder_path)
                                
                                # Extract business details
                                print("\nAttempting to extract business details...")
                                extract_business_details(driver, folder_path)
                                
                                print(f"All data has been saved to folder: {folder_path}")
                            else:
                                print("No case details were extracted. Please check if the search was successful.")
                            
                            # Wait for user to continue
                            input("Press ENTER to close the browser when finished viewing the results...")
                            
                        else:
                            print("Could not find search button with any strategy")
                            driver.save_screenshot("search_button_not_found.png")
                            print("Screenshot saved as 'search_button_not_found.png'")
                            
                            # Try direct JavaScript execution as a last resort
                            try:
                                print("Attempting to click search button using JavaScript...")
                                driver.execute_script("funViewCinoHistory();")
                                print("Executed JavaScript search function")
                                time.sleep(5)
                                driver.save_screenshot("js_search_results.png")
                                input("JavaScript search executed. Press ENTER to close the browser...")
                            except Exception as e:
                                print(f"JavaScript execution failed: {e}")
                            
                    else:
                        print("Could not find CAPTCHA input field with any strategy")
                        # Print page source to help debug
                        print("Page source excerpt:")
                        try:
                            page_source = driver.page_source
                            print(page_source[:500] + "..." + page_source[-500:])
                            with open("page_source_captcha.html", "w", encoding="utf-8") as f:
                                f.write(page_source)
                            print("Saved full page source to page_source_captcha.html")
                        except Exception:
                            print("Could not save page source")
                            
                        # Ask for manual continuation
                        proceed = input("Do you want to manually enter CAPTCHA in the browser and continue? (y/n): ")
                        if proceed.lower() == 'y':
                            print("Please manually enter CAPTCHA in the browser")
                            input("Press ENTER after entering CAPTCHA to attempt clicking the search button...")
                            
                            # Try to find and click search button
                            try:
                                search_button = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary")
                                search_button.click()
                                print("Clicked search button")
                                time.sleep(5)
                                driver.save_screenshot("manual_search_results.png")
                                
                                # Extract case details
                                case_data = extract_case_details(driver)
                                
                                if case_data:
                                    print("Successfully extracted case details")
                                    
                                    # Create folder and Excel file
                                    folder_path = create_case_folder(cnr_number, case_data)
                                    
                                    # Download PDF files if available
                                    if case_data.get("pdf_links", []):
                                        download_pdfs(driver, case_data["pdf_links"], folder_path)
                                    else:
                                        print("No PDF links found to download")
                                    
                                    # Extract and download order PDFs
                                    print("\nAttempting to download order PDFs...")
                                    extract_order_pdfs(driver, folder_path)
                                    
                                    # Extract business details
                                    print("\nAttempting to extract business details...")
                                    extract_business_details(driver, folder_path)
                                    
                                    print(f"All data has been saved to folder: {folder_path}")
                                else:
                                    print("No case details were extracted. Please check if the search was successful.")
                                
                                input("Press ENTER to close the browser...")
                            except Exception as e:
                                print(f"Could not click search button: {e}")
                            
                else:
                    print("Could not find CNR input field")
                    driver.save_screenshot("cnr_input_not_found.png")
                    
            except Exception as e:
                print(f"Error in CNR/CAPTCHA handling: {e}")
                traceback.print_exc()
                driver.save_screenshot("cnr_captcha_error.png")
                
        else:
            print("Could not find the District Court Services button with any strategy")
            
            # Save page source for debugging
            with open("page_source.html", "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            print("Saved page source to page_source.html")
            
            # Take a screenshot
            driver.save_screenshot("button_not_found.png")
            print("Saved screenshot to button_not_found.png")
    
    except Exception as e:
        print(f"Error: {e}")
        traceback.print_exc()
        if driver:
            driver.save_screenshot("error.png")
            print("Saved error screenshot to error.png")
    
    finally:
        # Close the browser only if user confirms
        if driver:
            close = input("Close the browser? (y/n): ")
            if close.lower() == 'y':
                print("Closing browser...")
                driver.quit()
            else:
                print("Browser will remain open. Close it manually when done.")
            
    print("Script completed.")

if __name__ == "__main__":
    main() 