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
    
# Wait for the feed to load after login
WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.ID, "global-nav")))

# 3. Open the Specific Search URL
search_url = "https://www.linkedin.com/search/results/people/?keywords=talent%20acquisition%20Amazon&origin=SWITCH_SEARCH_VERTICAL"
driver.get(search_url)

# Wait until search results are actually present
WebDriverWait(driver, 15).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]'))
)
time.sleep(2)  # Small extra buffer for all results to render

# 4. Click 'Connect' on the first available result
connect_containers = WebDriverWait(driver, 15).until(
    lambda d: d.find_elements(By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]')
)
print(f"  Found {len(connect_containers)} Connect button(s) on this page.")

idx = 2
container = connect_containers[idx]
connect_btn = WebDriverWait(container, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "a"))
)
person_name = connect_btn.get_attribute("aria-label") or "Unknown"
connect_btn.click()

driver.implicitly_wait(5)

root_element = driver.find_element(By.XPATH, '//*[@id="root"]')
print("root element",root_element)
c = root_element.find_elements(By.XPATH, './/div[@data-testid="interop-shadowdom"]')
print("c is ", c)
# artdeco_modal = c[0].shadow_root.find_element(By.CSS_SELECTOR, "#artdeco-modal-outlet" )
anbb = c[0].shadow_root.find_element(By.CSS_SELECTOR, "button[aria-label='Add a note']" )
print("anbb", anbb, anbb.get_attribute("innerHTML"))
anbb.click()

textarea = c[0].shadow_root.find_element(By.CSS_SELECTOR, "textarea[name='message']")

# wait for textarea to be interactable
WebDriverWait(c[0].shadow_root, 10).until(
    EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea[name='message']"))
)

# copy the message from connection_note.txt and send it
with open("connection_note.txt", "r") as f:
    message = f.read()
textarea.send_keys(message)

# locate send button and click it
send_btn = c[0].shadow_root.find_element(By.CSS_SELECTOR, "button[aria-label='Send invitation']")
send_btn.click()

# add wait for 20 mins
time.sleep(20 * 60)
