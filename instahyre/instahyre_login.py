import json
import os
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

CREDENTIAL_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "instahyre/credential_instahyre.json")
LOGIN_URL = "https://www.instahyre.com/login/"


def read_credentials():
    with open(CREDENTIAL_FILE, "r") as f:
        creds = json.load(f)
    return creds["email"], creds["password"]


def run_instahyre():
    email, password = read_credentials()

    driver = webdriver.Chrome()
    driver.maximize_window()
    driver.get(LOGIN_URL)

    wait = WebDriverWait(driver, 15)

    time.sleep(2)

    # Fill email
    email_input = wait.until(EC.presence_of_element_located((By.ID, "email")))
    email_input.clear()
    email_input.send_keys(email)

    time.sleep(3)

    # Fill password
    password_input = wait.until(EC.presence_of_element_located((By.ID, "password")))
    password_input.clear()
    password_input.send_keys(password)

    time.sleep(1)

    # Click Login button
    login_button = wait.until(EC.element_to_be_clickable(
        (By.CSS_SELECTOR, "#login-form button[type='submit']")
    ))
    login_button.click()

    # Wait for the page to load after login
    time.sleep(2)
    print("Instahyre login attempted successfully.")

    return driver
