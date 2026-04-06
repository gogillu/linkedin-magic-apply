import time
import random
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import (
    NoSuchElementException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
)
from linkedin.browser import driver
from linkedin.config import DELAY_BETWEEN_ACTIONS


def random_delay(min_sec=0.5, max_sec=1.5):
    """Sleep for a random duration between min_sec and max_sec."""
    import time, random
    time.sleep(random.uniform(min_sec, max_sec))


def dismiss_any_modal():
    """Try to close any overlay / modal that may have appeared."""
    selectors = [
        'button[aria-label="Dismiss"]',
        'button[aria-label="Got it"]',
        'button[aria-label="Close"]',
        'button.artdeco-modal__dismiss',
        'button.msg-overlay-bubble-header__control--new-convo-btn',
        'button.artdeco-toast-item__dismiss',
        'div.artdeco-modal button[data-test-modal-close-btn]',
        'div.send-invite button.artdeco-modal__dismiss',
    ]
    for sel in selectors:
        try:
            btns = driver.find_elements(By.CSS_SELECTOR, sel)
            for btn in btns:
                if btn.is_displayed():
                    btn.click()
                    random_delay(0.5, 1)
        except (NoSuchElementException, ElementClickInterceptedException,
                StaleElementReferenceException):
            pass
    try:
        from selenium import webdriver as wd
        wd.ActionChains(driver).send_keys(Keys.ESCAPE).perform()
        random_delay(0.5, 1)
    except Exception:
        pass


def scroll_to_bottom():
    """Scroll down the page gradually to load all results."""
    for _ in range(5):
        driver.execute_script("window.scrollBy(0, 600);")
        random_delay(0.8, 1.5)
    driver.execute_script("window.scrollTo(0, 0);")
    random_delay(1, 2)
