from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    ElementClickInterceptedException,
    NoSuchElementException,
    StaleElementReferenceException,
)
from linkedin.browser import driver, wait
from linkedin.config import CONNECTION_NOTE
from linkedin.utils import random_delay, dismiss_any_modal
import time
from datetime import datetime


def _send_note_via_shadow_dom(person_name):
    """Shared logic: handle the connection modal (add note / send without note / send invitation).
    Returns (modal_handled, note_sent, method)."""
    modal_handled = False
    note_sent = ""
    method = ""

    first_name = (
        person_name.replace("Invite ", "").split(" to connect")[0].split()[0]
        if "Invite" in person_name
        else person_name.split()[0] if person_name and person_name != "Unknown" else ""
    )
    personal_note = (
        CONNECTION_NOTE.replace("{name}", first_name)
        if first_name
        else CONNECTION_NOTE
    )

    # ── Path 1: Shadow DOM modal (search results page) ──

    # Option A: Add a note
    try:
        driver.implicitly_wait(1)
        root_element = driver.find_element(By.XPATH, '//*[@id="root"]')
        shadow_containers = root_element.find_elements(
            By.XPATH, './/div[@data-testid="interop-shadowdom"]'
        )
        if not shadow_containers:
            raise NoSuchElementException("No shadow DOM container found")

        shadow_root = shadow_containers[0].shadow_root
        add_note_btn = shadow_root.find_element(
            By.CSS_SELECTOR, "button[aria-label='Add a note']"
        )
        print(f"    Found 'Add a note' button (shadow DOM)")
        add_note_btn.click()
        random_delay(0.5, 1)

        textarea = shadow_root.find_element(
            By.CSS_SELECTOR, "textarea[name='message']"
        )
        WebDriverWait(shadow_root, 10).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "textarea[name='message']"))
        )
        textarea.clear()
        textarea.send_keys(personal_note)
        random_delay(0.5, 1)

        send_btn = shadow_root.find_element(
            By.CSS_SELECTOR, "button[aria-label='Send invitation']"
        )
        send_btn.click()
        modal_handled = True
        note_sent = personal_note
        method = "with note"
        print(f"    ✓ Sent (with note, shadow DOM)")
    except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as note_err:
        print(f"    ⚠ Shadow DOM add-a-note path failed: {type(note_err).__name__}: {note_err}")

    # Option B: Send without a note (shadow DOM)
    if not modal_handled:
        try:
            root_element = driver.find_element(By.XPATH, '//*[@id="root"]')
            shadow_containers = root_element.find_elements(
                By.XPATH, './/div[@data-testid="interop-shadowdom"]'
            )
            if shadow_containers:
                shadow_root = shadow_containers[0].shadow_root
                send_btn = shadow_root.find_element(
                    By.CSS_SELECTOR, "button[aria-label='Send without a note']"
                )
                send_btn.click()
                modal_handled = True
                method = "without note"
                print(f"    ✓ Sent (without note, shadow DOM)")
        except (NoSuchElementException, TimeoutException):
            pass

    # Option C: Plain Send / Send invitation (shadow DOM)
    if not modal_handled:
        try:
            root_element = driver.find_element(By.XPATH, '//*[@id="root"]')
            shadow_containers = root_element.find_elements(
                By.XPATH, './/div[@data-testid="interop-shadowdom"]'
            )
            if shadow_containers:
                shadow_root = shadow_containers[0].shadow_root
                send_btn = shadow_root.find_element(
                    By.CSS_SELECTOR,
                    "button[aria-label='Send invitation'], button[aria-label='Send now']"
                )
                send_btn.click()
                modal_handled = True
                method = "direct invitation"
                print(f"    ✓ Sent (invitation, shadow DOM)")
        except (NoSuchElementException, TimeoutException):
            pass

    # ── Path 2: Regular DOM / artdeco modal (profile page) ──

    # Option D: Add a note (regular DOM)
    if not modal_handled:
        try:
            print(f"    Trying regular DOM modal path...")
            # Look for "Add a note" button in artdeco modal
            add_note_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    '//button[@aria-label="Add a note"] | '
                    '//button[contains(@class,"artdeco-button")][.//span[text()="Add a note"]]'
                ))
            )
            print(f"    Found 'Add a note' button (regular DOM)")
            add_note_btn.click()
            random_delay(0.5, 1)

            # Find textarea in the modal
            textarea = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    '//textarea[@name="message"] | '
                    '//textarea[contains(@id,"custom-message")]'
                ))
            )
            textarea.clear()
            textarea.send_keys(personal_note)
            random_delay(0.5, 1)

            # Click send
            send_btn = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((
                    By.XPATH,
                    '//button[@aria-label="Send invitation"] | '
                    '//button[@aria-label="Send now"] | '
                    '//button[contains(@class,"artdeco-button--primary")][.//span[text()="Send"]]'
                ))
            )
            send_btn.click()
            modal_handled = True
            note_sent = personal_note
            method = "with note (regular DOM)"
            print(f"    ✓ Sent (with note, regular DOM)")
        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
            print(f"    ⚠ Regular DOM add-a-note path failed: {type(e).__name__}: {e}")

    # Option E: Send without a note (regular DOM)
    if not modal_handled:
        try:
            send_btn = driver.find_element(
                By.XPATH,
                '//button[@aria-label="Send without a note"] | '
                '//button[@aria-label="Send now"] | '
                '//button[contains(@class,"artdeco-button--primary")][.//span[text()="Send without a note"]]'
            )
            send_btn.click()
            modal_handled = True
            method = "without note (regular DOM)"
            print(f"    ✓ Sent (without note, regular DOM)")
        except (NoSuchElementException, TimeoutException):
            pass

    # Option F: Generic Send button (regular DOM)
    if not modal_handled:
        try:
            send_btn = driver.find_element(
                By.XPATH,
                '//div[contains(@class,"artdeco-modal")]//button[contains(@class,"artdeco-button--primary")]'
            )
            send_btn.click()
            modal_handled = True
            method = "direct send (regular DOM)"
            print(f"    ✓ Sent (direct, regular DOM)")
        except (NoSuchElementException, TimeoutException):
            pass

    if not modal_handled:
        print(f"    ⚠ No modal detected – request may have been sent directly.")
        method = "unknown/direct"

    return modal_handled, note_sent, method


def _handle_follow_person(profile_url, person_name):
    """Open a Follow person's profile in a new tab, click More → Connect, send note, close tab.
    Returns (success, modal_handled, note_sent, method)."""
    original_window = driver.current_window_handle

    try:
        # Open profile in new tab
        driver.execute_script("window.open(arguments[0], '_blank');", profile_url)
        random_delay(1, 2)

        # Switch to the new tab (last handle)
        new_tab = [h for h in driver.window_handles if h != original_window][-1]
        driver.switch_to.window(new_tab)
        random_delay(2, 3)

        # Wait for profile page to load
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))
        )

        dismiss_any_modal()
        random_delay(0.5, 1)

        # Close/minimize any expanded messaging overlay that may intercept clicks
        try:
            # Close all open message conversation windows
            msg_close_btns = driver.find_elements(
                By.CSS_SELECTOR,
                'button[data-control-name="overlay.close_conversation_window"], '
                'header.msg-overlay-bubble-header button.msg-overlay-bubble-header__control--new-convo-btn, '
                'button.msg-overlay-bubble-header__button--minimize, '
                'button[aria-label*="Close your"], '
                'button[aria-label*="Minimize"]'
            )
            for btn in msg_close_btns:
                try:
                    btn.click()
                    random_delay(0.3, 0.5)
                except Exception:
                    pass

            # Minimize the main messaging dock/widget if expanded
            msg_overlay = driver.find_elements(
                By.CSS_SELECTOR,
                'aside.msg-overlay-list-bubble--is-open button.msg-overlay-bubble-header__button, '
                'div.msg-overlay-list-bubble button.msg-overlay-bubble-header__button'
            )
            for btn in msg_overlay:
                try:
                    btn.click()
                    random_delay(0.3, 0.5)
                except Exception:
                    pass

            # Last resort: hide the entire messaging sidebar via JS
            driver.execute_script("""
                var msgOverlay = document.querySelector('aside.msg-overlay-list-bubble, div.msg-overlay-list-bubble');
                if (msgOverlay) { msgOverlay.style.display = 'none'; }
                var msgConvos = document.querySelectorAll('div.msg-convo-wrapper, div.msg-overlay-conversation-bubble');
                msgConvos.forEach(function(el) { el.style.display = 'none'; });
            """)
            random_delay(0.3, 0.5)
        except Exception:
            pass

        print(f"    ✓ Messaging overlay collapsed/hidden. Now looking for 'More' button...")

        # Scroll to top of profile actions area to ensure "More" button is in view
        try:
            driver.execute_script("window.scrollTo(0, 0);")
            random_delay(1, 1.5)
        except Exception:
            pass

        # NOTE: We intentionally do NOT click Follow here.
        # We only want to connect (with a note), not follow without a note.

        # Click the 3-dots "More" button on the profile — try multiple strategies
        more_btn = None

        # Strategy 1: aria-label="More" with aria-expanded attribute (profile 3-dots button)
        try:
            # The profile 3-dots button has aria-expanded, nav "More" does not
            more_candidates = driver.find_elements(
                By.CSS_SELECTOR,
                'button[aria-label="More"][aria-expanded]'
            )
            if more_candidates:
                # Prefer the one near profile actions (not in nav)
                for candidate in more_candidates:
                    # Check it's not inside the nav bar
                    try:
                        candidate.find_element(By.XPATH, './ancestor::nav')
                        continue  # skip nav buttons
                    except NoSuchElementException:
                        more_btn = candidate
                        break
                if not more_btn and more_candidates:
                    more_btn = more_candidates[0]

            if more_btn:
                WebDriverWait(driver, 3).until(EC.element_to_be_clickable(more_btn))
                print(f"    Found 'More' (3-dots) button via aria-label='More' + aria-expanded")
            else:
                raise NoSuchElementException("No matching More button with aria-expanded")
        except (TimeoutException, NoSuchElementException):
            print(f"    ⚠ Strategy 1 (aria-label='More' + aria-expanded) failed")

        # Strategy 2: aria-label="More" (broader, new LinkedIn HTML)
        if not more_btn:
            try:
                more_candidates = driver.find_elements(
                    By.CSS_SELECTOR, 'button[aria-label="More"]'
                )
                # Filter out nav buttons
                for candidate in more_candidates:
                    try:
                        candidate.find_element(By.XPATH, './ancestor::nav')
                        continue
                    except NoSuchElementException:
                        more_btn = candidate
                        break
                if more_btn:
                    print(f"    Found 'More' (3-dots) button via aria-label='More' (filtered)")
                else:
                    raise NoSuchElementException("No non-nav More button found")
            except (NoSuchElementException, TimeoutException):
                print(f"    ⚠ Strategy 2 (aria-label='More' filtered) failed")

        # Strategy 3: ID ending in -profile-overflow-action (old)
        if not more_btn:
            try:
                more_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    'button[id$="-profile-overflow-action"]'
                )
                print(f"    Found 'More' button via id selector")
            except NoSuchElementException:
                print(f"    ⚠ Strategy 3 (id selector) failed")

        # Strategy 4: aria-label="More actions" (old)
        if not more_btn:
            try:
                more_btn = driver.find_element(
                    By.CSS_SELECTOR,
                    'button[aria-label="More actions"]'
                )
                print(f"    Found 'More' button via aria-label='More actions' selector")
            except NoSuchElementException:
                print(f"    ⚠ Strategy 4 (aria-label='More actions') failed")

        # Strategy 5: artdeco-dropdown trigger containing span "More" (old)
        if not more_btn:
            try:
                more_btn = driver.find_element(
                    By.XPATH,
                    '//div[contains(@class,"artdeco-dropdown")]//button[contains(@class,"artdeco-dropdown__trigger")]/span[text()="More"]/parent::button'
                )
                print(f"    Found 'More' button via XPath span text")
            except NoSuchElementException:
                print(f"    ⚠ Strategy 5 (XPath span text) failed")

        # Strategy 6: scan all non-nav buttons for overflow/3-dots icon or "More" text
        if not more_btn:
            try:
                buttons = driver.find_elements(By.TAG_NAME, "button")
                for btn in buttons:
                    try:
                        # Skip nav buttons
                        try:
                            btn.find_element(By.XPATH, './ancestor::nav')
                            continue
                        except NoSuchElementException:
                            pass
                        # Check for overflow SVG icon (3 dots)
                        svgs = btn.find_elements(By.CSS_SELECTOR, 'svg[id*="overflow"]')
                        if svgs:
                            more_btn = btn
                            print(f"    Found 'More' (3-dots) button via overflow SVG scan")
                            break
                        # Check for span text "More"
                        spans = btn.find_elements(By.TAG_NAME, "span")
                        for span in spans:
                            if span.text.strip() == "More":
                                more_btn = btn
                                print(f"    Found 'More' button via button text scan")
                                break
                        if more_btn:
                            break
                    except StaleElementReferenceException:
                        continue
            except Exception:
                print(f"    ⚠ Strategy 6 (button scan) failed")

        if not more_btn:
            print(f"    ✗ Could not find 'More' button on profile for {person_name} after all strategies")
            driver.close()
            driver.switch_to.window(original_window)
            return False, False, "", ""

        print(f"    Scrolling to 'More' button and clicking...")
        driver.execute_script("arguments[0].scrollIntoView({block:'center'});", more_btn)
        random_delay(0.5, 1)

        # Attempt JS click, with retry using regular click as fallback
        try:
            driver.execute_script("arguments[0].click();", more_btn)
            print(f"    ✓ 'More' button JS-clicked")
        except Exception as e1:
            print(f"    ⚠ JS click failed: {e1}, trying regular click...")
            try:
                more_btn.click()
                print(f"    ✓ 'More' button regular-clicked")
            except Exception as e2:
                print(f"    ✗ Regular click also failed: {e2}")
                driver.close()
                driver.switch_to.window(original_window)
                return False, False, "", ""

        random_delay(1, 1.5)
        print(f"    Dropdown should be open. Looking for 'Connect' option...")

        # Click "Connect" from the dropdown
        connect_option = None

        # Strategy 1: div with aria-label containing "to connect" (new LinkedIn HTML)
        try:
            connect_option = WebDriverWait(driver, 5).until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR,
                    'div[aria-label*="to connect"]'
                ))
            )
            print(f"    Found 'Connect' option via div[aria-label*='to connect']")
        except (TimeoutException, NoSuchElementException):
            print(f"    ⚠ Connect Strategy 1 (div aria-label) failed")

        # Strategy 2: any element with aria-label containing "to connect"
        if not connect_option:
            try:
                connect_option = driver.find_element(
                    By.CSS_SELECTOR,
                    '[aria-label*="to connect"]'
                )
                print(f"    Found 'Connect' option via [aria-label*='to connect']")
            except NoSuchElementException:
                print(f"    ⚠ Connect Strategy 2 (any aria-label) failed")

        # Strategy 3: old artdeco-dropdown__item with aria-label
        if not connect_option:
            try:
                connect_option = driver.find_element(
                    By.CSS_SELECTOR,
                    'div.artdeco-dropdown__item[aria-label*="to connect"]'
                )
                print(f"    Found 'Connect' option via artdeco-dropdown__item")
            except NoSuchElementException:
                print(f"    ⚠ Connect Strategy 3 (artdeco-dropdown__item) failed")

        # Strategy 4: old artdeco-dropdown__item with role="button"
        if not connect_option:
            try:
                items = driver.find_elements(
                    By.CSS_SELECTOR, 'div.artdeco-dropdown__item[role="button"]'
                )
                for item in items:
                    aria = item.get_attribute("aria-label") or ""
                    if "connect" in aria.lower():
                        connect_option = item
                        print(f"    Found 'Connect' option via artdeco role=button scan")
                        break
            except Exception:
                pass

        # Strategy 5: scan visible divs/elements for text "Connect" inside the dropdown area
        if not connect_option:
            try:
                # Look for any clickable element containing "Connect" text that appeared after clicking More
                candidates = driver.find_elements(
                    By.XPATH,
                    '//div[contains(@aria-label,"connect") or contains(@aria-label,"Connect")]'
                )
                for c in candidates:
                    if c.is_displayed():
                        connect_option = c
                        print(f"    Found 'Connect' option via XPath aria-label scan")
                        break
            except Exception:
                pass

        # Strategy 6: find <p> or <span> with text "Connect" and click its parent div
        if not connect_option:
            try:
                connect_texts = driver.find_elements(
                    By.XPATH,
                    '//p[normalize-space(text())="Connect"]/ancestor::div[@aria-label] | '
                    '//span[normalize-space(text())="Connect"]/ancestor::div[@aria-label]'
                )
                for ct in connect_texts:
                    aria = ct.get_attribute("aria-label") or ""
                    if "connect" in aria.lower() and ct.is_displayed():
                        connect_option = ct
                        print(f"    Found 'Connect' option via text ancestor scan")
                        break
            except Exception:
                print(f"    ⚠ Connect Strategy 6 (text scan) failed")

        if not connect_option:
            print(f"    ✗ Could not find 'Connect' in More dropdown for {person_name}")
            driver.close()
            driver.switch_to.window(original_window)
            return False, False, "", ""

        print(f"    Clicking 'Connect' option...")
        try:
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", connect_option)
            random_delay(0.3, 0.5)
            driver.execute_script("arguments[0].click();", connect_option)
            print(f"    ✓ 'Connect' option JS-clicked")
        except Exception:
            try:
                connect_option.click()
                print(f"    ✓ 'Connect' option regular-clicked")
            except Exception as e:
                print(f"    ✗ Could not click 'Connect' option: {e}")
                driver.close()
                driver.switch_to.window(original_window)
                return False, False, "", ""

        random_delay(1, 1.5)

        # Now use the shared note-sending logic
        modal_handled, note_sent, method = _send_note_via_shadow_dom(person_name)
        random_delay(0.5, 1)
        dismiss_any_modal()

        # Close the tab and switch back
        driver.close()
        driver.switch_to.window(original_window)
        random_delay(0.5, 1)

        return True, modal_handled, note_sent, method

    except Exception as e:
        print(f"    ✗ Error handling Follow person {person_name}: {type(e).__name__}: {e}")
        # Make sure we close the tab and go back
        try:
            if driver.current_window_handle != original_window:
                driver.close()
            driver.switch_to.window(original_window)
        except Exception:
            driver.switch_to.window(original_window)
        return False, False, "", ""


def send_connection_requests_on_page(remaining=None, max_req_to_people=10, log_callback=None):
    """Find all Connect buttons on the current page and click them.
    Also handle Follow buttons by opening profiles in new tabs.
    Returns (sent_count, log_entries) where log_entries is a list of dicts."""
    sent = 0
    log_entries = []

    # ── New selectors based on updated LinkedIn HTML ──
    # Connect buttons: <a aria-label="Invite ... to connect" href="/preload/search-custom-invite/...">
    # Follow buttons:  <button aria-label="Follow ...">

    # Try new selectors first, fall back to old ones
    follow_buttons = driver.find_elements(
        By.CSS_SELECTOR, 'button[aria-label^="Follow "]'
    )
    # Filter out non-person follow buttons (e.g. company follow)
    follow_buttons = [
        btn for btn in follow_buttons
        if btn.get_attribute("aria-label") and "Follow " in btn.get_attribute("aria-label")
    ]
    # Fallback: old selector
    if not follow_buttons:
        follow_containers_old = driver.find_elements(
            By.CSS_SELECTOR, '[data-view-name="edge-creation-follow-action"]'
        )
        print(f"  Found {len(follow_containers_old)} Follow button(s) via old selector.")
    else:
        print(f"  Found {len(follow_buttons)} Follow button(s) on this page (new selector).")

    connect_links = driver.find_elements(
        By.CSS_SELECTOR, 'a[aria-label*="to connect"]'
    )
    # Fallback: old selector
    if not connect_links:
        connect_containers_old = driver.find_elements(
            By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]'
        )
        print(f"  Found {len(connect_containers_old)} Connect button(s) via old selector.")
    else:
        print(f"  Found {len(connect_links)} Connect button(s) on this page (new selector).")

    # --- Process Follow buttons FIRST (open profile in new tab → More → Connect) ---
    follow_people = []

    # New HTML: each follow button has aria-label="Follow <Name>", profile URL is in ancestor listitem
    for btn in follow_buttons:
        try:
            aria = btn.get_attribute("aria-label") or ""
            person_name = aria.replace("Follow ", "").strip() if aria.startswith("Follow") else "Unknown"

            # Navigate up to the listitem container, then find the profile link
            try:
                listitem = btn.find_element(By.XPATH, './ancestor::div[@role="listitem"]')
                profile_link = listitem.find_element(
                    By.CSS_SELECTOR, 'a[href*="/in/"]'
                )
                profile_url = profile_link.get_attribute("href")
            except NoSuchElementException:
                # Fallback: try ancestor <a>
                try:
                    parent_link = btn.find_element(By.XPATH, './ancestor::a[@href]')
                    profile_url = parent_link.get_attribute("href")
                except NoSuchElementException:
                    profile_url = None

            if profile_url and "/in/" in profile_url:
                follow_people.append((profile_url, person_name))
        except (StaleElementReferenceException, NoSuchElementException):
            continue

    # Fallback: old selector path
    if not follow_people:
        try:
            follow_containers = driver.find_elements(
                By.CSS_SELECTOR, '[data-view-name="edge-creation-follow-action"]'
            )
            for fc in follow_containers:
                try:
                    parent_link = fc.find_element(By.XPATH, './ancestor::a[@href]')
                    profile_url = parent_link.get_attribute("href")
                    try:
                        follow_btn = fc.find_element(By.CSS_SELECTOR, "button")
                        aria = follow_btn.get_attribute("aria-label") or ""
                        person_name = aria.replace("Follow ", "").strip() if aria.startswith("Follow") else aria
                    except Exception:
                        person_name = "Unknown"
                    if profile_url and "/in/" in profile_url:
                        follow_people.append((profile_url, person_name))
                except Exception:
                    continue
        except Exception:
            pass

    print(f"  Collected {len(follow_people)} Follow person profile(s) to process.")

    for profile_url, person_name in follow_people:
        if remaining is not None and sent >= remaining:
            print(f"  Reached per-company limit, stopping.")
            break
        if sent >= max_req_to_people:
            print(f"  Reached max requests per page, stopping.")
            break

        print(f"  → Follow person: {person_name} ({profile_url})")
        success, modal_handled, note_sent, method = _handle_follow_person(profile_url, person_name)

        if success:
            sent += 1
            entry = {
                "person_name": person_name,
                "method": f"follow→profile: {method}",
                "note": note_sent,
                "status": "sent" if modal_handled else "possibly sent",
                "timestamp": datetime.now().isoformat(),
                "page_url": profile_url,
            }
            log_entries.append(entry)
            if log_callback:
                log_callback(entry)
        else:
            print(f"    ✗ Could not send connection to {person_name}")

    # --- Process Connect buttons SECOND ---
    # New HTML: connect buttons are <a aria-label="Invite X to connect">
    # Re-query each iteration to avoid stale refs
    num_connect = len(connect_links) if connect_links else 0
    # Fallback count from old selector
    if not connect_links:
        connect_containers_old = driver.find_elements(
            By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]'
        )
        num_connect = len(connect_containers_old)

    for idx in range(min(num_connect, max_req_to_people)):
        if remaining is not None and sent >= remaining:
            print(f"  Reached per-company limit, stopping.")
            break
        if sent >= max_req_to_people:
            print(f"  Reached max requests per page, stopping.")
            break

        try:
            dismiss_any_modal()
            random_delay(0.3, 0.8)

            # Re-query connect buttons (new selector first, then old)
            current_connect = driver.find_elements(
                By.CSS_SELECTOR, 'a[aria-label*="to connect"]'
            )
            use_old_selector = False
            if not current_connect:
                current_connect = driver.find_elements(
                    By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]'
                )
                use_old_selector = True

            if idx >= len(current_connect):
                break

            if use_old_selector:
                container = current_connect[idx]
                connect_btn = container.find_element(By.CSS_SELECTOR, "a")
            else:
                connect_btn = current_connect[idx]

            person_name = connect_btn.get_attribute("aria-label") or "Unknown"
            print(f"  → Clicking: {person_name}")

            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", connect_btn
            )
            random_delay(0.5, 1)

            # Retry click up to 3 times if intercepted
            click_success = False
            for attempt in range(3):
                try:
                    connect_btn.click()
                    click_success = True
                    break
                except ElementClickInterceptedException:
                    print(f"    ⚠ Click intercepted (attempt {attempt + 1}/3), dismissing overlay …")
                    dismiss_any_modal()
                    random_delay(0.5, 1)
                    try:
                        current_connect = driver.find_elements(
                            By.CSS_SELECTOR, 'a[aria-label*="to connect"]'
                        )
                        if not current_connect:
                            current_connect = driver.find_elements(
                                By.CSS_SELECTOR, '[data-view-name="edge-creation-connect-action"]'
                            )
                            if idx < len(current_connect):
                                connect_btn = current_connect[idx].find_element(By.CSS_SELECTOR, "a")
                            else:
                                break
                        else:
                            if idx < len(current_connect):
                                connect_btn = current_connect[idx]
                            else:
                                break
                        driver.execute_script(
                            "arguments[0].scrollIntoView({block:'center'});", connect_btn
                        )
                        random_delay(0.5, 1)
                    except Exception:
                        break

            if not click_success:
                print(f"    ✗ Skipped (could not click after retries)")
                continue

            modal_handled, note_sent, method = _send_note_via_shadow_dom(person_name)
            random_delay(0.5, 1)
            dismiss_any_modal()
            sent += 1

            entry = {
                "person_name": person_name,
                "method": method,
                "note": note_sent,
                "status": "sent" if modal_handled else "possibly sent",
                "timestamp": datetime.now().isoformat(),
                "page_url": driver.current_url,
            }
            log_entries.append(entry)
            if log_callback:
                log_callback(entry)

        except (
            StaleElementReferenceException,
            ElementClickInterceptedException,
            TimeoutException,
            NoSuchElementException,
        ) as e:
            print(f"    ✗ Skipped ({type(e).__name__})")
            dismiss_any_modal()
            random_delay(0.5, 1)
            continue

    return sent, log_entries


def go_to_next_page():
    """Click the 'Next' pagination button. Returns True if successful."""
    try:
        next_btn = driver.find_element(
            By.CSS_SELECTOR, 'button[data-testid="pagination-controls-next-button-visible"]'
        )
        if next_btn.is_enabled():
            driver.execute_script(
                "arguments[0].scrollIntoView({block:'center'});", next_btn
            )
            random_delay(0.5, 1)
            next_btn.click()
            random_delay(0.5, 1)
            return True
    except NoSuchElementException:
        pass
    return False
