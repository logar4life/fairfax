from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.common.exceptions import TimeoutException, WebDriverException, NoSuchElementException
import time
import os
from datetime import date
from bs4 import BeautifulSoup
import pandas as pd
import csv
import requests
import re
from PIL import Image
from selenium.webdriver.common.action_chains import ActionChains
import base64
from io import BytesIO

# User credentials
USER_ID = "XAMOTAH"
PASSWORD = "Logar4life!"

# URLs
LOGIN_URL = "https://www.fairfaxcounty.gov/myfairfax/auth/forms/ffx-choose-login.jsp"
CPAN_URL = "https://ccr.fairfaxcounty.gov/cpan/"

def setup_driver():
    """Setup Chrome driver with proper configuration"""
    chrome_options = Options()
    chrome_options.headless = True  # Headless is False to open browser window
    
    # Add options to prevent timeout issues
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-gpu")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_argument("--disable-plugins")
    chrome_options.add_argument("--disable-web-security")
    chrome_options.add_argument("--allow-running-insecure-content")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--disable-background-timer-throttling")
    chrome_options.add_argument("--disable-backgrounding-occluded-windows")
    chrome_options.add_argument("--disable-renderer-backgrounding")
    chrome_options.add_argument("--disable-features=TranslateUI")
    chrome_options.add_argument("--disable-ipc-flooding-protection")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    
    download_dir = os.path.abspath(os.path.join("fairfax_pdfs"))
    prefs = {
        "download.default_directory": download_dir,
        "download.prompt_for_download": False,
        "download.directory_upgrade": True,
        "safebrowsing.enabled": True
    }
    chrome_options.add_experimental_option("prefs", prefs)
    
    try:
        # Setup WebDriver with timeout
        service = Service(ChromeDriverManager().install())
        driver = webdriver.Chrome(service=service, options=chrome_options)
        
        # Set timeouts
        driver.set_page_load_timeout(120)  # Increased to 120 seconds
        driver.implicitly_wait(15)  # Increased to 15 seconds
        
        return driver
    except Exception as e:
        print(f"Error setting up Chrome driver: {e}")
        return None

def safe_click(driver, element, wait_time=2):
    """Safely click an element with retry logic"""
    max_retries = 3
    for attempt in range(max_retries):
        try:
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.5)
            element.click()
            time.sleep(wait_time)
            return True
        except Exception as e:
            print(f"Click attempt {attempt + 1} failed: {e}")
            if attempt < max_retries - 1:
                time.sleep(1)
                continue
            else:
                print("All click attempts failed")
                return False

def wait_for_element_with_retry(driver, by, value, timeout=15, max_retries=3):
    """Wait for element with retry logic"""
    for attempt in range(max_retries):
        try:
            wait = WebDriverWait(driver, timeout)
            element = wait.until(EC.presence_of_element_located((by, value)))
            return element
        except TimeoutException:
            print(f"Timeout waiting for element {value} (attempt {attempt + 1}/{max_retries})")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                raise
        except Exception as e:
            print(f"Error waiting for element {value}: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
            else:
                raise

def extract_all_tables_to_csv(page_source, output_prefix="fairfax_results"):
    soup = BeautifulSoup(page_source, "html.parser")
    tables = soup.find_all("table", class_="k-grid-table k-table k-table-md k-selectable")
    if not tables:
        print("No results tables found on the page.")
        return

    for idx, table in enumerate(tables):
        # Extract headers (only visible columns)
        headers = []
        thead = table.find("thead")
        if thead:
            header_row = thead.find("tr")
            if header_row:
                for th in header_row.find_all("th"):
                    style = th.get("style", "")
                    if "display: none" not in style:
                        col_title = th.find("span", class_="k-column-title")
                        if col_title:
                            headers.append(col_title.get_text(strip=True))
                        else:
                            headers.append(th.get_text(strip=True))
        # Extract rows (only visible columns)
        rows = []
        tbody = table.find("tbody")
        if tbody:
            for tr in tbody.find_all("tr"):
                row = []
                tds = tr.find_all("td")
                for td in tds:
                    style = td.get("style", "")
                    if "display: none" not in style:
                        row.append(td.get_text(strip=True))
                if row:
                    rows.append(row)
        # Write to CSV
        filename = f"{output_prefix}_table{idx+1}.csv" if len(tables) > 1 else f"{output_prefix}.csv"
        with open(filename, "w", newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            if headers:
                writer.writerow(headers)
            writer.writerows(rows)
        print(f"Exported table {idx+1} to {filename} with {len(rows)} rows.")

def take_fullpage_screenshot(driver, save_path):
    """Take a full-page screenshot using Chrome DevTools Protocol."""
    # This requires Chrome >= 59 and Selenium 4+
    # Use Chrome DevTools Protocol for full-page screenshot
    metrics = driver.execute_cdp_cmd("Page.getLayoutMetrics", {})
    width = metrics["contentSize"]["width"]
    height = metrics["contentSize"]["height"]
    driver.set_window_size(width, height)
    time.sleep(1)
    driver.save_screenshot(save_path)
    print(f"Full-page screenshot saved to {save_path}")
    return save_path

def send_image_to_openai(image_path, prompt="Extract all visible data from this screenshot and return as text."):
    """Send an image to OpenAI Vision API and return the response text."""
    import os
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY environment variable not set.")
    with open(image_path, "rb") as f:
        image_bytes = f.read()
    base64_image = base64.b64encode(image_bytes).decode("utf-8")
    client = openai.OpenAI(api_key=api_key)
    response = client.chat.completions.create(
        model="gpt-4-vision-preview",
        messages=[
            {"role": "user", "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{base64_image}"}}
            ]}
        ],
        max_tokens=1024
    )
    return response.choices[0].message.content

def screenshot_and_extract():
    """Open the Document page, take a screenshot, send to OpenAI, and print extracted data."""
    driver = setup_driver()
    try:
        print("Opening Document page...")
        driver.get("https://ccr.fairfaxcounty.gov/cpan/Document")
        time.sleep(5)  # Wait for page to load
        screenshot_path = os.path.join("fairfax", "cpan_document_fullpage.png")
        take_fullpage_screenshot(driver, screenshot_path)
        print("Sending screenshot to OpenAI Vision API...")
        extracted_text = send_image_to_openai(screenshot_path)
        print("\n--- Extracted Data from OpenAI Vision API ---\n")
        print(extracted_text)
    finally:
        driver.quit()

def main():
    driver = None
    try:
        print("Setting up Chrome driver...")
        driver = setup_driver()
        
        if driver is None:
            print("Failed to setup Chrome driver. Exiting...")
            return
        
        wait = WebDriverWait(driver, 20)  # Increased wait time to 20 seconds
        
        # Open the login page
        print("Opening login page...")
        driver.get(LOGIN_URL)
        
        # Wait for the page to load and find login elements
        print("Waiting for login form to load...")
        try:
            username_field = wait_for_element_with_retry(driver, By.ID, "username")
            password_field = driver.find_element(By.ID, "password")
        except Exception as e:
            print(f"Could not find login form elements: {e}")
            print("Trying alternative selectors...")
            # Try alternative selectors
            try:
                username_field = wait_for_element_with_retry(driver, By.NAME, "username")
                password_field = driver.find_element(By.NAME, "password")
            except:
                username_field = wait_for_element_with_retry(driver, By.XPATH, "//input[@type='text']")
                password_field = driver.find_element(By.XPATH, "//input[@type='password']")
        
        # Fill in the username and password
        print("Entering credentials...")
        username_field.clear()
        username_field.send_keys(USER_ID)
        password_field.clear()
        password_field.send_keys(PASSWORD)
        
        # Click the submit button
        print("Submitting login form...")
        try:
            submit_button = driver.find_element(By.XPATH, "//input[@type='submit']")
        except:
            submit_button = driver.find_element(By.XPATH, "//button[@type='submit']")
        
        safe_click(driver, submit_button, 3)
        
        # Wait for login to complete
        print("Waiting for login to complete...")
        time.sleep(8)  # Increased wait time for login processing
        
        # Check if login was successful
        try:
            # Look for some element that indicates successful login
            wait.until(EC.presence_of_element_located((By.XPATH, "//*[contains(text(), 'Welcome') or contains(text(), 'Dashboard') or contains(text(), 'MyFairfax')]")))
            print("Login successful!")
        except:
            print("Login status unclear, proceeding anyway...")
        
        # Navigate to CPAN page
        print("Navigating to CPAN page...")
        driver.get(CPAN_URL)

        # Wait for the main search button to be clickable and click it
        print("Waiting for search panel button...")
        try:
            search_button = wait_for_element_with_retry(driver, By.ID, "SearchButton")
            safe_click(driver, search_button, 2)
            print("Search panel button clicked.")
        except Exception as e:
            print(f"Could not click search panel button: {e}")
            # The search panel might already be open. Let's try to continue.
            pass
        
        time.sleep(2) # Increased wait for panel to open

        # Click on 'Land Records'
        print("Selecting 'Land Records'...")
        try:
            land_records_button = wait_for_element_with_retry(driver, By.ID, "SideMenu_LandRecords")
            safe_click(driver, land_records_button, 2)
        except Exception as e:
            print(f"Could not click 'Land Records' button: {e}")

        # Select "DOCUMENT TYPE" from the search type dropdown
        print("Selecting 'DOCUMENT TYPE' from dropdown...")
        try:
            search_type_dropdown = Select(wait_for_element_with_retry(driver, By.ID, "LR_SearchType_SearchBy"))
            search_type_dropdown.select_by_value("3")
            time.sleep(2)  # Wait for dropdown to update
        except Exception as e:
            print(f"Could not select 'DOCUMENT TYPE': {e}")

        # Wait for the select element to be present
        try:
            deed_doc_type_select = Select(wait_for_element_with_retry(driver, By.ID, "deedDocTypeDT"))

            # Deselect all first (optional, but good practice)
            deed_doc_type_select.deselect_all()

            # List of values to select
            values_to_select = ["LP", "ST"]  # Add more as needed

            for value in values_to_select:
                deed_doc_type_select.select_by_value(value)
                time.sleep(1)  # Small wait between selections
        except Exception as e:
            print(f"Could not select document types: {e}")

        # Select "ALL" from the sub-type dropdown
        print("Selecting 'ALL' from sub-type dropdown...")
        # Using a brittle XPath as provided by the user. This might need adjustment.
        all_dropdown_xpath = "/html/body/div[1]/form/div/div/div[2]/div/div/div[2]/div/div[2]/div/div[4]/div/div/div[2]/div/select"
        try:
            all_dropdown = Select(wait_for_element_with_retry(driver, By.XPATH, all_dropdown_xpath))
            all_dropdown.select_by_value("")
        except Exception as e:
            print(f"Could not select 'ALL' from the dropdown. It may not exist for this document type. Error: {e}")

        # Set date range
        print("Setting date range...")
        # Select '7 Days Ago' from the dropdown if present
        try:
            range_dropdown = Select(wait_for_element_with_retry(driver, By.ID, "Search_LRStartDate"))
            range_dropdown.select_by_visible_text("7 Days Ago")
            print("Selected '7 Days Ago' from date range dropdown.")
        except Exception as e:
            print(f"Could not select '7 Days Ago' from dropdown: {e}")
        
        today = date.today()
        start_date = today.replace(day=1)
        start_date_str = start_date.strftime("%m/%d/%Y")
        end_date_str = today.strftime("%m/%d/%Y")

        try:
            start_date_input = wait_for_element_with_retry(driver, By.ID, "LR_startdate")
            driver.execute_script("arguments[0].value = arguments[1];", start_date_input, start_date_str)

            end_date_input = wait_for_element_with_retry(driver, By.ID, "LR_enddate")
            driver.execute_script("arguments[0].value = arguments[1];", end_date_input, end_date_str)
        except Exception as e:
            print(f"Could not set date range: {e}")
        
        # Click the search button
        print("Clicking search button...")
        try:
            final_search_button = wait_for_element_with_retry(driver, By.ID, "Search")
            safe_click(driver, final_search_button, 3)
        except Exception as e:
            print(f"Could not click search button: {e}")

        print(f"Search for {values_to_select} completed. Waiting for results to load...")
        # Wait for results table to load (up to 60 seconds)
        table_xpath = "/html/body/div[1]/div/div/div[3]/table"
        try:
            table_elem = wait_for_element_with_retry(driver, By.XPATH, table_xpath, timeout=60)
            print("Results table appeared!")
            
            # Take screenshot of the search results page
            print("Taking screenshot of search results page...")
            screenshot_folder = os.path.join("fairfax", "screenshots")
            if not os.path.exists(screenshot_folder):
                os.makedirs(screenshot_folder)
            
            # Generate filename with timestamp
            from datetime import datetime
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            screenshot_filename = f"search_results_{timestamp}.png"
            screenshot_path = os.path.join(screenshot_folder, screenshot_filename)
            
            # Take screenshot
            driver.save_screenshot(screenshot_path)
            print(f"Screenshot saved to: {screenshot_path}")
            
            # Highlight table border red, header yellow, rows green
            driver.execute_script('arguments[0].style.border = "3px solid red";', table_elem)
            driver.execute_script('var ths = arguments[0].querySelectorAll("thead tr"); for (var i=0; i<ths.length; ++i) { ths[i].style.background = "yellow"; }', table_elem)
            driver.execute_script('var trs = arguments[0].querySelectorAll("tbody tr"); for (var i=0; i<trs.length; ++i) { trs[i].style.background = "lightgreen"; }', table_elem)

            # --- UPDATED LOGIC: For each row, click the details icon to open the PDF details page ---
            # Remove pdf_folder logic
            # Screenshot folder for all details page screenshots
            screenshot_folder = os.path.join("fairfax", "screenshots")
            if not os.path.exists(screenshot_folder):
                os.makedirs(screenshot_folder)
            screenshot_filenames = []
            main_window = driver.current_window_handle
            print("Iterating over table rows to download PDFs from details icon...")
            rows = table_elem.find_elements(By.XPATH, ".//tbody/tr")
            for i, row in enumerate(rows):
                try:
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if not cells:
                        continue
                    # Find the <img class="imgIcon" src="../Images/ImageIcon.gif"> in the row
                    details_icon = None
                    try:
                        details_icon = row.find_element(By.XPATH, ".//img[contains(@class, 'imgIcon') and contains(@src, 'ImageIcon.gif')]")
                    except:
                        details_icon = None
                    if details_icon:
                        print(f"Row {i+1}: Found details icon, clicking to open details page...")
                        try:
                            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", details_icon)
                            time.sleep(0.5)
                            driver.execute_script("arguments[0].click();", details_icon)
                        except Exception as e:
                            print(f"Row {i+1}: Could not click details icon via JS: {e}")
                        time.sleep(3)  # Increased wait for new tab to open
                        # Switch to new tab
                        window_handles = driver.window_handles
                        if len(window_handles) > 1:
                            new_tab = [h for h in window_handles if h != main_window][0]
                            driver.switch_to.window(new_tab)
                            time.sleep(3)  # Increased wait for page to load
                            
                            # --- Open page in full screen mode ---
                            try:
                                driver.maximize_window()
                                print(f"Row {i+1}: Opened page in full screen mode")
                            except Exception as e:
                                print(f"Row {i+1}: Could not maximize window: {e}")

                            # --- Take screenshot of the details page immediately after opening ---
                            try:
                                screenshot_filename = f"doc{i+1}.png"
                                screenshot_path = os.path.join(screenshot_folder, screenshot_filename)
                                driver.save_screenshot(screenshot_path)
                                screenshot_filenames.append(screenshot_filename)
                                print(f"Row {i+1}: Details page screenshot saved as {screenshot_path}")
                            except Exception as e:
                                print(f"Row {i+1}: Could not take details page screenshot: {e}")
                            # No PDF or TIFF download logic, only screenshots
                            # Close the new tab and switch back
                            driver.close()
                            driver.switch_to.window(main_window)
                            time.sleep(2)  # Increased wait
                        else:
                            print(f"Row {i+1}: No new tab opened after clicking details icon.")
                    else:
                        print(f"Row {i+1}: No details icon found in row.")
                except Exception as e:
                    print(f"Row {i+1}: Error processing row: {e}")
                    continue
            print("Finished iterating rows for PDF download.")
            # Write all screenshot filenames to a text file
            try:
                screenshots_list_path = os.path.join(screenshot_folder, "screenshots_list.txt")
                with open(screenshots_list_path, "w", encoding="utf-8") as f:
                    for fname in screenshot_filenames:
                        f.write(fname + "\n")
                print(f"Screenshot filenames written to {screenshots_list_path}")
            except Exception as e:
                print(f"Could not write screenshots list: {e}")
            # --- END UPDATED LOGIC ---
        except Exception as e:
            print(f"Table did not appear after waiting: {e}")
        
        # Fetch data from results table and export to CSV
        print("Fetching results and exporting to CSV...")
        data_found = False
        try:
            page_source = driver.page_source
            # Only extract the table at the specified XPath
            soup = BeautifulSoup(page_source, "html.parser")
            table = soup.select_one('body > div:nth-of-type(1) > div > div > div:nth-of-type(3) > table')
            if table:
                tables = [table]
            else:
                tables = []
            if tables:
                for idx, table in enumerate(tables):
                    headers = []
                    thead = table.find("thead")
                    if thead:
                        header_row = thead.find("tr")
                        if header_row:
                            for th in header_row.find_all("th"):
                                style = th.get("style", "")
                                if "display: none" not in style:
                                    col_title = th.find("span", class_="k-column-title")
                                    if col_title:
                                        headers.append(col_title.get_text(strip=True))
                                    else:
                                        headers.append(th.get_text(strip=True))
                    rows = []
                    tbody = table.find("tbody")
                    if tbody:
                        for tr in tbody.find_all("tr"):
                            row = []
                            tds = tr.find_all("td")
                            for td in tds:
                                style = td.get("style", "")
                                if "display: none" not in style:
                                    row.append(td.get_text(strip=True))
                            if row:
                                rows.append(row)
                    filename = os.path.join("fairfax", f"fairfax_results.csv")
                    with open(filename, "w", newline='', encoding='utf-8') as f:
                        writer = csv.writer(f)
                        if headers:
                            writer.writerow(headers)
                        writer.writerows(rows)
                    print(f"Exported table to {filename} with {len(rows)} rows.")
                data_found = True
            else:
                print("No results table found at the specified XPath.")
        except Exception as e:
            print(f"Error exporting results to CSV: {e}")

        if data_found:
            if driver:
                driver.quit()
            return

        # If not the last document type, go back to the search page to prepare for the next search
        if values_to_select != ["LP", "ST"]:
            print("Returning to search page for next search...")
            # It's better to click a 'New Search' or 'Modify Search' button if available
            # but for now we will just re-apply the search criteria on the same page.
            # Assuming the search results page keeps the search form.
            
            # Re-select "DOCUMENT TYPE" as page state might have changed
            print("Re-selecting 'DOCUMENT TYPE' from dropdown...")
            try:
                search_type_dropdown = Select(wait_for_element_with_retry(driver, By.ID, "LR_SearchType_SearchBy"))
                search_type_dropdown.select_by_value("3")
            except Exception as e:
                print(f"Could not re-select 'DOCUMENT TYPE': {e}")

        # Keep the browser open for a while to observe the result
        print("All searches completed. Keeping browser open for 5 minutes...")
        time.sleep(400)

    except TimeoutException as e:
        print(f"Timeout error occurred: {e}")
        if driver:
            print("Current URL:", driver.current_url)
            print("Page title:", driver.title)
        time.sleep(10)  # Keep browser open longer for debugging
    except WebDriverException as e:
        print(f"WebDriver error occurred: {e}")
        if driver:
            print("Current URL:", driver.current_url)
            print("Page title:", driver.title)
        time.sleep(10)  # Keep browser open longer for debugging
    except Exception as e:
        print(f"An error occurred: {e}")
        if driver:
            print("Current URL:", driver.current_url)
            print("Page title:", driver.title)
        time.sleep(10)  # Keep browser open longer for debugging

    finally:
        # Close the browser
        if driver:
            print("Browser will remain open as requested.")
            pass

if __name__ == "__main__":
    main()
