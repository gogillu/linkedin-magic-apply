import json
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from webdriver_manager.chrome import ChromeDriverManager
import time

# Read credentials from a file
def get_credentials():
    with open('credential.json') as cred_file:
        return json.load(cred_file)

# Get LinkedIn credentials
credentials = get_credentials()
linkedin_email = credentials['email']
linkedin_password = credentials['password']

# Set up ChromeDriver
service = Service(ChromeDriverManager().install())
driver = webdriver.Chrome(service=service)

# Open LinkedIn login page
driver.get('https://www.linkedin.com/login')

# Wait for the login elements to be present
wait = WebDriverWait(driver, 10)
email_input = wait.until(EC.presence_of_element_located((By.ID, 'username')))
password_input = driver.find_element(By.ID, 'password')

# Enter credentials and log in
email_input.send_keys(linkedin_email)
password_input.send_keys(linkedin_password)
driver.find_element(By.XPATH, "//button[@type='submit']").click()

# Wait for the home page to load
wait.until(EC.presence_of_element_located((By.XPATH, "//input[@aria-label='Search']")))

# Open the LinkedIn search URL
url = 'https://www.linkedin.com/search/results/people/?keywords=talent%20acquisition%20groww&origin=GLOBAL_SEARCH_HEADER&page=2&sid=41w'
driver.get(url)

# Wait for the page to load
wait.until(EC.presence_of_element_located((By.XPATH, "//button[contains(@aria-label, 'Invite')]")))

# Iterate over the list of people and perform the required actions
people = driver.find_elements(By.XPATH, "//button[contains(@aria-label, 'Invite')]")

for person in people:
    try:
        # Scroll into view and click on the connect button
        ActionChains(driver).move_to_element(person).perform()
        time.sleep(1)  # Allow some time for the element to come into view
        person.click()
        
        # Wait for a while to see the response on the UI
        time.sleep(3)
        
        # Wait for the "Add a note" button to appear and click it
        add_note_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Add a note')]")))
        add_note_button.click()
        
        # Write the message
        message_box = wait.until(EC.presence_of_element_located((By.XPATH, "//textarea[@name='message']")))
        message_box.send_keys(
            "Hello,\n\n"
            "Could you please consider me for backend SDE2 roles at your org. I have 4+ years of software dev experience.\n\n"
            "my resume: https://shorturl.at/rQynz\n\n"
            "I am expert in problem-solving, transforming requirements into sustainable software with quality code...\n\n"
            "I'm serving notice period."
        )
        
        # Find the "Send" button by its aria-label and click it
        send_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Send invitation']")))
        send_button.click()
        
        # Wait for a while to see the response on the UI
        time.sleep(5)
        
    except Exception as e:
        print(f"Skipping person due to error: {e}")
        continue

# Close the driver
driver.quit()
