import time
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException

from instahyre.instahyre_login import run_instahyre


def apply_to_jobs():
    driver = run_instahyre()
    time.sleep(30)
    wait = WebDriverWait(driver, 25)

    # Wait for "View »" button to appear
    view_button = wait.until(EC.element_to_be_clickable(
        (By.ID, "interested-btn")
    ))
    view_button.click()
    time.sleep(15)

    while True:
        try:
            # Wait for popup and click "Apply"
            apply_button = wait.until(EC.element_to_be_clickable(
                (By.CSS_SELECTOR, "div.apply button.btn-primary")
            ))
            apply_button.click()
            print("Applied to a job.")

            time.sleep(15)

        except (TimeoutException, Exception) as e:
            print(f"Primary apply button not found: {e}")
            try:
                # Look for bulk Apply button
                bulk_apply_button = wait.until(EC.element_to_be_clickable(
                    (By.CSS_SELECTOR, "button.btn-success[ng-click='applyBulk()']")
                ))
                bulk_apply_button.click()
                print("Clicked bulk Apply button.")
                time.sleep(12)
                continue
            except (TimeoutException, Exception):
                print("No more buttons found. Done applying.")
                break

    driver.quit()


if __name__ == "__main__":
    apply_to_jobs()
