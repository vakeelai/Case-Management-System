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
from sqlalchemy import create_engine
from urllib.parse import urljoin
from twocaptcha import TwoCaptcha

solver = TwoCaptcha('6e8f5fdfb967c46f1589fb420d52579f')

def solve_captcha(driver, wait, retries=3):
    for attempt in range(retries):
        try:
            print(f"Attempt {attempt+1} to solve CAPTCHA...")
            captcha_img = wait.until(EC.presence_of_element_located((By.ID, "captcha_image")))
            temp_file = f'temp_captcha_{attempt}.png'
            captcha_img.screenshot(temp_file)

            result = solver.normal(file=temp_file)
            os.remove(temp_file)

            if result and 'code' in result:
                print(f"CAPTCHA solved: {result['code']}")
                return result['code']
            else:
                print("Invalid response from 2Captcha.")
        except Exception as e:
            print(f"Error solving CAPTCHA: {e}")
    print("All attempts failed.")
    return None



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
                        # Try to find label within the cell
                        labels = label_cell.find_elements(By.TAG_NAME, "label")
                        if labels:
                            key = labels[0].text.strip()
                        else:
                            key = label_cell.text.strip()
                            
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
    
    # Create Excel file with case data AND load to PostgreSQL
    if case_data:
        try:
            # Remove PDF links from dictionary
            pdf_links = case_data.pop("pdf_links", [])

            # Create DataFrame from case data
            df = pd.DataFrame([case_data])

            # Rename columns to match PostgreSQL table
            df.rename(columns={
                'Filing Number': 'filing_number',
                'Registration Number': 'registration_number',
                'CNR Number': 'cnr_number',
                'Status_First Hearing Date': 'status_first_hearing_date',
                'Status_Next Hearing Date': 'status_next_hearing_date',
                'Status_Case Stage': 'status_case_stage',
                'Status_Court Number and Judge': 'status_court_number_and_judge'
            }, inplace=True)

            # Save to Excel
            excel_path = os.path.join(folder_name, f"{folder_name}_case_details.xlsx")
            df.to_excel(excel_path, index=False)
            print(f"Saved case details to Excel: {excel_path}")

            # Save to PostgreSQL
            engine = create_engine("postgresql+psycopg2://postgres:1951@localhost:5432/postgres")
            df.to_sql('ecourts_high_courts', engine, schema='public', if_exists='append', index=False)
            print("Data successfully inserted into PostgreSQL table: public.ecourts_high_courts")

            return pdf_links, folder_name
        except Exception as e:
            print(f"Error saving Excel or inserting to DB: {e}")
            traceback.print_exc()

    
    return [], folder_name

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
            button = driver.find_element(By.CSS_SELECTOR, 'a[href="http://hcservices.ecourts.gov.in/"][title="District Court Services"]')
            print("Found button by href and title")
        except Exception as e:
            print(f"Strategy 1 failed: {e}")
        
        # Strategy 2: Find by href only
        if button is None:
            try:
                print("Strategy 2: Find by href only...")
                button = driver.find_element(By.CSS_SELECTOR, 'a[href="https://hcservices.ecourts.gov.in/"]')
                print("Found button by href")
            except Exception as e:
                print(f"Strategy 2 failed: {e}")
        
        # Strategy 3: Find by title only
        if button is None:
            try:
                print("Strategy 3: Find by title only...")
                button = driver.find_element(By.CSS_SELECTOR, 'a[title="High courts Services"]')
                print("Found button by title")
            except Exception as e:
                print(f"Strategy 3 failed: {e}")
        
        # Strategy 4: Find by link text
        if button is None:
            try:
                print("Strategy 4: Find by link text...")
                button = driver.find_element(By.LINK_TEXT, "High courts Services")
                print("Found button by link text")
            except Exception as e:
                print(f"Strategy 4 failed: {e}")
                
        # Strategy 5: Find by partial link text
        if button is None:
            try:
                print("Strategy 5: Find by partial link text...")
                button = driver.find_element(By.PARTIAL_LINK_TEXT, "High courts")
                print("Found button by partial link text")
            except Exception as e:
                print(f"Strategy 5 failed: {e}")
                
        # Strategy 6: Find by XPath containing text
        if button is None:
            try:
                print("Strategy 6: Find by XPath...")
                button = driver.find_element(By.XPATH, "//a[contains(text(), 'High courts Services')]")
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
                        
                        # Solve CAPTCHA automatically
                        captcha_value = solve_captcha(driver, wait)
                        if not captcha_value:
                            print("CAPTCHA solving failed. Exiting...")
                            return

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
                                pdf_links, folder_path = create_case_folder(cnr_number, case_data)
                                
                                # Download PDF files if available
                                if pdf_links:
                                    download_pdfs(driver, pdf_links, folder_path)
                                else:
                                    print("No PDF links found to download")
                                
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
                                    pdf_links, folder_path = create_case_folder(cnr_number, case_data)
                                    
                                    # Download PDF files if available
                                    if pdf_links:
                                        download_pdfs(driver, pdf_links, folder_path)
                                    else:
                                        print("No PDF links found to download")
                                    
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