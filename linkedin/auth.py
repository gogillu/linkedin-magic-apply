from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException
from linkedin.browser import driver, wait
from linkedin.config import EMAIL, PASSWORD
from linkedin.utils import random_delay


def login():
    """Log in to LinkedIn."""
    print("[*] Navigating to LinkedIn login …")
    driver.get("https://www.linkedin.com/login")
    random_delay(2, 4)

    email_field = wait.until(EC.presence_of_element_located((By.ID, "username")))
    email_field.clear()
    email_field.send_keys(EMAIL)

    password_field = driver.find_element(By.ID, "password")
    password_field.clear()
    password_field.send_keys(PASSWORD)

    random_delay(1, 2)
    driver.find_element(By.CSS_SELECTOR, 'button[type="submit"]').click()

    try:
        wait.until(
            lambda d: "/feed" in d.current_url
            or "/search" in d.current_url
            or "/check" in d.current_url
            or "/checkpoint" in d.current_url
        )
    except TimeoutException:
        pass

    if "checkpoint" in driver.current_url or "check" in driver.current_url:
        print("[!] Security checkpoint detected – please solve it manually.")
        input("    Press ENTER here once you are past the checkpoint …")

    print("[✓] Logged in successfully.")
    random_delay(1, 2)
