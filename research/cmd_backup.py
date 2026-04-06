import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

# 1. Setup Driver
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()))
driver.maximize_window()

# 2. Login to LinkedIn
driver.get("https://www.linkedin.com/login")
    
driver.find_element(By.ID, "username").send_keys("mail.govind.c@gmail.com")
driver.find_element(By.ID, "password").send_keys("linkedin!dnivog12")
driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
# Wait for the feed to load
# WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.ID, "global-nav")))

# 3. Open the Specific Search URL
search_url = "https://www.linkedin.com/search/results/people/?keywords=talent%20acquisition%20Amazon&origin=SWITCH_SEARCH_VERTICAL"
driver.get(search_url)

# 4. Click 'Connect' on the first available result
# We use a wait to ensure the results are loaded
# connect_button = WebDriverWait(driver, 10).until(EC.element_to_be_clickable((By.XPATH, "//button[contains(@aria-label, 'Connect')]")))
# time.sleep(5)  # Wait for the page to load results

# driver wait 5 sec
driver.implicitly_wait(10)

connect_containers = driver.find_elements(By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]')
print(f"  Found {len(connect_containers)} Connect button(s) on this page.")

# for idx in range(len(connect_containers)):
idx = 1
containers = driver.find_elements(By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]')
# if idx >= len(containers):
#     break
container = containers[idx]
connect_btn = container.find_element(By.CSS_SELECTOR, "a")
person_name = connect_btn.get_attribute("aria-label") or "Unknown"
connect_btn.click()



driver.implicitly_wait(10)
# time.sleep(4)  # Wait for the modal to appear
# anb = driver.find_element(By.CSS_SELECTOR, "button[aria-label='Add a note']")

root_element = driver.find_element(By.XPATH, '//*[@id="root"]')
# c = root_element.find_elements(By.XPATH, ".//div")
c = root_element.find_elements(By.XPATH, './/div[@data-testid="interop-shadowdom"]')
anbb = c[0].shadow_root.find_element(By.CSS_SELECTOR, "#artdeco-modal-outlet" )
anbb.click()


# import pyautogui
# import time

# pyautogui.click(950, 980)
















# # 5. Click 'Add a note' in the pop-up
# add_note_button = WebDriverWait(driver, 5).until(
#     EC.element_to_be_clickable((By.XPATH, "//button[@aria-label='Add a note']"))
# )
# add_note_button.click()

# print("Successfully reached the 'Add a note' stage.")
# # You can now use .send_keys("Your message") on the text area if needed.
