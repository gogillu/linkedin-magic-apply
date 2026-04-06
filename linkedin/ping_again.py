import os
import re
import json
from datetime import datetime, timedelta
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    StaleElementReferenceException,
    ElementClickInterceptedException,
)
from linkedin.browser import driver, wait
from linkedin.config import CONNECTION_NOTE
from linkedin.utils import random_delay


PA_LOG_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs_pa")
os.makedirs(PA_LOG_DIR, exist_ok=True)

PA_CONFIG_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "pa_config.json")
DEFAULT_MAX_CONVERSATIONS = 20
DEFAULT_MIN_DAYS = 2
MESSAGING_URL = "https://www.linkedin.com/messaging/"


def _load_pa_config():
    config = {
        "max_conversations": DEFAULT_MAX_CONVERSATIONS,
        "min_days_between_pings": DEFAULT_MIN_DAYS,
    }
    if os.path.isfile(PA_CONFIG_FILE):
        try:
            with open(PA_CONFIG_FILE, "r", encoding="utf-8") as f:
                user_config = json.load(f)
            config.update(user_config)
        except Exception as e:
            print(f"[!] Could not load pa_config.json: {e}")
    return config


def _parse_linkedin_date(text):
    """Parse LinkedIn's various date/time formats from sidebar and thread headings.

    LinkedIn formats observed:
      Sidebar:
        - "3:06 PM"            → today
        - "Mar 26"             → this year (no year = current year)
        - "Dec 24, 2025"       → explicit year
        - "Sep 9, 2025"        → explicit year
        - "Jan 23, 2023"       → old year
      Thread headings (uppercase):
        - "TODAY"              → today
        - "YESTERDAY"          → yesterday
        - "WEDNESDAY"          → most recent past Wednesday
        - "MAR 30"             → this year
        - "JAN 18"             → this year
        - "SEP 9, 2025"       → explicit year
        - "MAR 12, 2021"      → explicit year
      Relative:
        - "1d", "2w", "3h", "just now"

    Returns a datetime or None.
    """
    if not text:
        return None

    text = text.strip()
    text_lower = text.lower()
    now = datetime.now()

    # --- Special keywords ---
    if text_lower in ("today", "just now", "now"):
        return now
    if text_lower == "yesterday":
        return now - timedelta(days=1)

    # --- Day-of-week names (e.g. "Wednesday", "MONDAY") → most recent past occurrence ---
    day_names = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
    if text_lower in day_names:
        target_dow = day_names.index(text_lower)  # 0=Mon ... 6=Sun
        current_dow = now.weekday()
        days_back = (current_dow - target_dow) % 7
        if days_back == 0:
            days_back = 7  # "Monday" on a Monday means last Monday
        return now - timedelta(days=days_back)

    # --- Relative timestamps: "1d", "2w", "3h" ---
    match = re.match(r"^(\d+)\s*(s|m|min|h|d|w|mo|y)$", text_lower)
    if match:
        value = int(match.group(1))
        unit = match.group(2)
        deltas = {
            "s": timedelta(seconds=value),
            "m": timedelta(minutes=value),
            "min": timedelta(minutes=value),
            "h": timedelta(hours=value),
            "d": timedelta(days=value),
            "w": timedelta(weeks=value),
            "mo": timedelta(days=value * 30),
            "y": timedelta(days=value * 365),
        }
        if unit in deltas:
            return now - deltas[unit]

    # --- Time only: "3:06 PM", "8:39 AM" → today ---
    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
        try:
            t = datetime.strptime(text, fmt).time()
            return datetime.combine(now.date(), t)
        except ValueError:
            pass

    # --- Date with explicit year: "Dec 24, 2025", "SEP 9, 2025", "Mar 12, 2021" ---
    for fmt in ("%b %d, %Y", "%B %d, %Y"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            pass

    # --- Date without year: "Mar 26", "MAR 30", "Jan 18" → this year, but if in future roll back ---
    for fmt in ("%b %d", "%B %d"):
        try:
            parsed = datetime.strptime(text, fmt)
            parsed = parsed.replace(year=now.year)
            if parsed > now:
                parsed = parsed.replace(year=now.year - 1)
            return parsed
        except ValueError:
            pass

    return None
    return None


def _get_sidebar_timestamps():
    """Use JS to read all sidebar conversation timestamps at once.
    Returns list of {'index': i, 'text': '3:06 PM'/'Mar 26'/etc.} dicts."""
    try:
        return driver.execute_script("""
            var items = document.querySelectorAll(
                'li.msg-conversation-listitem, li.msg-conversations-container__convo-item'
            );
            var result = [];
            items.forEach(function(li, idx) {
                var timeEl = li.querySelector(
                    'time, [class*="time-stamp"], [class*="timestamp"]'
                );
                result.push({
                    index: idx,
                    text: timeEl ? (timeEl.getAttribute('datetime') || timeEl.innerText.trim()) : ''
                });
            });
            return result;
        """) or []
    except Exception:
        return []


def _scroll_until_old_enough(min_days, max_conversations):
    """Scroll the sidebar and return the index of the first conversation
    that is >= min_days old. Also loads conversations up to max_conversations.
    Returns (start_index, total_loaded)."""
    try:
        list_container = driver.find_element(
            By.CSS_SELECTOR,
            "ul.msg-conversations-container__conversations-list, "
            "div.msg-conversations-container__conversations-list"
        )
    except NoSuchElementException:
        print("[!] Could not find conversation list container.")
        return 0, 0

    now = datetime.now()
    start_index = None
    loaded = 0
    stale_rounds = 0

    while stale_rounds < 5:
        new_loaded = len(driver.find_elements(
            By.CSS_SELECTOR,
            "li.msg-conversation-listitem, li.msg-conversations-container__convo-item"
        ))
        if new_loaded == loaded:
            stale_rounds += 1
        else:
            stale_rounds = 0
        loaded = new_loaded

        # Check sidebar timestamps to find the first one that's old enough
        sidebar_ts = _get_sidebar_timestamps()
        for item in sidebar_ts:
            ts_text = item.get("text", "")
            if not ts_text:
                continue
            # Try ISO datetime attr first
            parsed = None
            try:
                parsed = datetime.fromisoformat(
                    ts_text.replace("Z", "+00:00")
                ).replace(tzinfo=None)
            except (ValueError, AttributeError):
                parsed = _parse_linkedin_date(ts_text)
            if parsed and (now - parsed).days >= min_days:
                start_index = item["index"]
                break

        if start_index is not None:
            print(f"[*] Found eligible conversation at index {start_index} "
                  f"(sidebar: {sidebar_ts[start_index].get('text')!r}). "
                  f"Loaded {loaded} total.", flush=True)
            # Load a few more pages beyond the start_index to have a buffer
            for _ in range(3):
                driver.execute_script(
                    "arguments[0].scrollTop = arguments[0].scrollHeight;", list_container
                )
                random_delay(0.8, 1.2)
            loaded = len(driver.find_elements(
                By.CSS_SELECTOR,
                "li.msg-conversation-listitem, li.msg-conversations-container__convo-item"
            ))
            break

        if loaded >= max_conversations:
            print(f"[*] Reached max_conversations ({max_conversations}) without finding eligible ones.", flush=True)
            break

        # Scroll down to load more
        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight;", list_container
        )
        random_delay(1, 2)

    # Scroll the sidebar so the start_index item is visible
    if start_index is not None:
        try:
            items = driver.find_elements(
                By.CSS_SELECTOR,
                "li.msg-conversation-listitem, li.msg-conversations-container__convo-item"
            )
            if start_index < len(items):
                driver.execute_script(
                    "arguments[0].scrollIntoView({block: 'center'});", items[start_index]
                )
                random_delay(0.5, 1)
        except Exception:
            pass
    else:
        start_index = 0

    total = min(loaded, max_conversations)
    return start_index, total


def _get_conversation_items(max_conversations):
    items = driver.find_elements(
        By.CSS_SELECTOR,
        "li.msg-conversation-listitem, li.msg-conversations-container__convo-item"
    )
    return items[:max_conversations]


def _get_person_name_from_conversation_item(conv):
    """Extract person name from a conversation list item."""
    selectors = [
        "h3.msg-conversation-listitem__participant-names span",
        "h3 span.truncate",
        "span.msg-conversation-listitem__participant-names",
        "h3.msg-conversation-listitem__participant-names",
    ]
    for sel in selectors:
        try:
            el = conv.find_element(By.CSS_SELECTOR, sel)
            name = el.text.strip()
            if name:
                return name
        except NoSuchElementException:
            continue
    return None


def _conversation_preview_starts_with_you(conv):
    """Check if the conversation preview line starts with 'You:' (we sent last msg)."""
    selectors = [
        "p.msg-conversation-listitem__message-snippet",
        "span.msg-conversation-listitem__message-snippet",
        "p.msg-conversation-card__message-snippet-body",
    ]
    for sel in selectors:
        try:
            el = conv.find_element(By.CSS_SELECTOR, sel)
            preview = el.text.strip()
            if preview.lower().startswith("you:"):
                return True, preview
            return False, preview
        except NoSuchElementException:
            continue
    return None, None


def _get_last_message_info():
    """Read the last message in the currently open conversation.
    Returns (sender_is_me, message_text, parsed_timestamp)."""

    # Scroll to bottom of the message thread
    try:
        msg_list = driver.find_element(
            By.CSS_SELECTOR,
            "div.msg-s-message-list-content, ul.msg-s-message-list-content"
        )
        driver.execute_script(
            "arguments[0].scrollTop = arguments[0].scrollHeight;", msg_list
        )
        random_delay(0.5, 1)
    except NoSuchElementException:
        pass

    # Collect all message events
    events = driver.find_elements(
        By.CSS_SELECTOR, "li.msg-s-message-list__event"
    )
    if not events:
        return None, None, None

    last_event = events[-1]

    # --- Determine sender ---
    sender_is_me = False
    classes = (last_event.get_attribute("class") or "")
    # LinkedIn adds "--other" for messages from the other person
    if "msg-s-event-listitem--other" in classes:
        sender_is_me = False
    else:
        sender_is_me = True

    # --- Message text ---
    message_text = None
    body_selectors = [
        "p.msg-s-event-listitem__body",
        "div.msg-s-event-listitem__body",
        "span.msg-s-event-listitem__body",
        ".msg-s-event-listitem__message-bubble p",
        ".msg-s-event-listitem__message-bubble",
    ]
    for sel in body_selectors:
        try:
            el = last_event.find_element(By.CSS_SELECTOR, sel)
            txt = el.text.strip()
            if txt:
                message_text = txt
                break
        except NoSuchElementException:
            continue

    # --- Timestamp ---
    # LinkedIn messaging shows timestamps in two ways:
    #   1. Date headings like "TODAY", "YESTERDAY", "Apr 1" in the thread
    #   2. Time labels like "3:10 PM" next to message groups
    # We use JS scoped to the message thread panel to get the right one.
    parsed_ts = None

    try:
        ts_data = driver.execute_script("""
            // Find the message thread container
            var thread = document.querySelector(
                '.msg-s-message-list-content, .msg-s-message-list, [class*="msg-s-message-list"]'
            );
            if (!thread) return null;

            var result = {};

            // 1. Get the last date heading (TODAY, WEDNESDAY, MAR 30, etc.)
            var dateHeadings = thread.querySelectorAll(
                '.msg-s-message-list__time-heading, [class*="time-heading"], h4, h3'
            );
            var lastDateText = null;
            for (var i = dateHeadings.length - 1; i >= 0; i--) {
                var t = dateHeadings[i].innerText.trim();
                if (t) { lastDateText = t; break; }
            }
            result.dateHeading = lastDateText;

            // 2. Get the last <time> inside the thread only
            var times = thread.querySelectorAll('time');
            var lastTimeEl = times.length > 0 ? times[times.length - 1] : null;
            if (lastTimeEl) {
                result.datetime = lastTimeEl.getAttribute('datetime');
                result.title = lastTimeEl.getAttribute('title');
                result.text = lastTimeEl.innerText.trim();
            }

            // 3. Grab the sidebar timestamp text for the currently active conversation
            //    This is the most reliable: "3:06 PM", "Mar 26", "Sep 9, 2025" etc.
            var activeConv = document.querySelector(
                'li.msg-conversation-listitem--active, '
                + 'li[class*="msg-conversation-listitem"][class*="active"]'
            );
            if (activeConv) {
                // The sidebar date is usually in a <time> element or a small text span
                var timeEl = activeConv.querySelector('time');
                if (timeEl) {
                    result.sidebarDatetime = timeEl.getAttribute('datetime');
                    result.sidebarTitle = timeEl.getAttribute('title');
                    result.sidebarText = timeEl.innerText.trim();
                }
                // Also grab any visible text that looks like a date (near the name)
                var dateSpans = activeConv.querySelectorAll(
                    'time, [class*="time-stamp"], [class*="timestamp"], span.msg-conversation-listitem__time-stamp'
                );
                for (var j = 0; j < dateSpans.length; j++) {
                    var st = dateSpans[j].innerText.trim();
                    if (st) {
                        result.sidebarVisibleText = st;
                        break;
                    }
                }
            }

            return result;
        """)

        if ts_data:
            print(f"    [DEBUG-TS] dateHeading={ts_data.get('dateHeading')!r} "
                  f"threadTime={{datetime={ts_data.get('datetime')!r}, title={ts_data.get('title')!r}, text={ts_data.get('text')!r}}} "
                  f"sidebar={{datetime={ts_data.get('sidebarDatetime')!r}, title={ts_data.get('sidebarTitle')!r}, "
                  f"text={ts_data.get('sidebarText')!r}, visible={ts_data.get('sidebarVisibleText')!r}}}",
                  flush=True)

            # Priority 1: <time datetime="..."> ISO attribute (most precise if available)
            for key in ("datetime", "sidebarDatetime"):
                dt_val = ts_data.get(key)
                if dt_val:
                    try:
                        parsed_ts = datetime.fromisoformat(
                            dt_val.replace("Z", "+00:00")
                        ).replace(tzinfo=None)
                        break
                    except (ValueError, AttributeError):
                        pass

            # Priority 2: Sidebar visible text — "3:06 PM", "Mar 26", "Sep 9, 2025"
            #   This is the most reliable human-readable indicator
            if parsed_ts is None:
                for key in ("sidebarVisibleText", "sidebarText", "sidebarTitle"):
                    val = (ts_data.get(key) or "").strip()
                    if val:
                        parsed_ts = _parse_linkedin_date(val)
                        if parsed_ts:
                            break

            # Priority 3: Thread date heading — "TODAY", "WEDNESDAY", "MAR 30", "SEP 9, 2025"
            #   Combine with time text if possible (heading=date, text=time of day)
            if parsed_ts is None:
                date_heading = (ts_data.get("dateHeading") or "").strip()
                time_text = (ts_data.get("text") or ts_data.get("title") or "").strip()

                heading_dt = _parse_linkedin_date(date_heading)
                if heading_dt:
                    # Try to parse time portion like "3:10 PM" and combine
                    time_part = None
                    for fmt in ("%I:%M %p", "%I:%M%p", "%H:%M"):
                        try:
                            time_part = datetime.strptime(time_text, fmt).time()
                            break
                        except ValueError:
                            continue
                    if time_part:
                        parsed_ts = datetime.combine(heading_dt.date(), time_part)
                    else:
                        parsed_ts = heading_dt

            # Priority 4: Thread time text alone (might be "3:10 PM" = today)
            if parsed_ts is None:
                time_text = (ts_data.get("text") or ts_data.get("title") or "").strip()
                if time_text:
                    parsed_ts = _parse_linkedin_date(time_text)

    except Exception as e:
        print(f"    [DEBUG-TS] JS timestamp extraction error: {e}", flush=True)

    return sender_is_me, message_text, parsed_ts


def _send_message(message_text):
    """Type @mention (first dropdown option = receiver), then the message, and send."""
    from selenium.webdriver.common.action_chains import ActionChains

    try:
        msg_input = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                'div.msg-form__contenteditable[contenteditable="true"], '
                'div[role="textbox"][contenteditable="true"]'
            ))
        )

        # --- Clear the input properly: click, Ctrl+A, Delete ---
        msg_input.click()
        random_delay(0.3, 0.5)
        ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
        random_delay(0.1, 0.2)
        ActionChains(driver).send_keys(Keys.DELETE).perform()
        random_delay(0.3, 0.5)

        # --- Type @ to trigger mention dropdown ---
        # Use ActionChains (realistic key events) for the single @ character
        ActionChains(driver).click(msg_input).pause(0.3).send_keys("@").perform()
        random_delay(1.5, 2)

        # Try to find and click the first mention dropdown option
        mention_found = False
        mention_selectors = [
            'div[class*="msg-mentions"] li',
            'ul[class*="mentions"] li',
            'div[class*="mention"] [role="option"]',
            '[class*="typeahead"] li',
            '[class*="typeahead"] [role="option"]',
            '[role="listbox"] [role="option"]',
            'ul[role="listbox"] li',
        ]

        # Strategy 1: Click the dropdown option via CSS
        for sel in mention_selectors:
            try:
                first_option = WebDriverWait(driver, 3).until(
                    EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                )
                first_option.click()
                mention_found = True
                print("    [DEBUG] @mention selected via CSS.", flush=True)
                break
            except TimeoutException:
                continue

        # Strategy 2: JS execCommand to insert @ + fire events
        if not mention_found:
            print("    [DEBUG] CSS failed, trying JS execCommand for @.", flush=True)
            # Clear again
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            random_delay(0.1, 0.2)
            ActionChains(driver).send_keys(Keys.DELETE).perform()
            random_delay(0.3, 0.5)

            driver.execute_script("""
                var el = arguments[0];
                el.focus();
                document.execCommand('insertText', false, '@');
            """, msg_input)
            random_delay(1.5, 2)

            for sel in mention_selectors:
                try:
                    first_option = WebDriverWait(driver, 3).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, sel))
                    )
                    first_option.click()
                    mention_found = True
                    print("    [DEBUG] @mention selected after JS execCommand.", flush=True)
                    break
                except TimeoutException:
                    continue

        # Strategy 3: Keyboard Down + Enter
        if not mention_found:
            print("    [DEBUG] Trying keyboard Down+Enter.", flush=True)
            ActionChains(driver).send_keys(Keys.ARROW_DOWN).pause(0.3).send_keys(Keys.ENTER).perform()
            random_delay(0.5, 0.8)
            content = msg_input.get_attribute("innerHTML") or ""
            mention_found = "data-" in content or len(content) > 5

        if mention_found:
            random_delay(0.3, 0.5)
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            random_delay(0.2, 0.3)
        else:
            print("    [WARN] @mention failed. Sending without @mention.", flush=True)
            ActionChains(driver).key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).perform()
            random_delay(0.1, 0.2)
            ActionChains(driver).send_keys(Keys.DELETE).perform()
            random_delay(0.2, 0.3)

        # --- Type the message FAST using JS execCommand (not char by char) ---
        # Replace newlines with execCommand insertParagraph for line breaks
        driver.execute_script("""
            var el = arguments[0];
            var text = arguments[1];
            el.focus();
            var lines = text.split('\\n');
            for (var i = 0; i < lines.length; i++) {
                document.execCommand('insertText', false, lines[i]);
                if (i < lines.length - 1) {
                    document.execCommand('insertLineBreak', false, null);
                }
            }
        """, msg_input, message_text)
        random_delay(0.5, 1)

        send_btn = WebDriverWait(driver, 5).until(
            EC.element_to_be_clickable((
                By.CSS_SELECTOR,
                "button.msg-form__send-button, "
                'button[type="submit"].msg-form__send-btn, '
                "button.msg-form__send-btn"
            ))
        )
        send_btn.click()
        random_delay(1, 2)
        return True
    except (TimeoutException, NoSuchElementException) as e:
        print(f"    [!] Failed to send message: {e}")
        return False


def ping_again():
    """Iterate the messaging list and re-ping people whose last message
    was sent by us, starts with 'Hello', and is older than min_days."""

    config = _load_pa_config()
    max_conversations = config.get("max_conversations", DEFAULT_MAX_CONVERSATIONS)
    min_days = config.get("min_days_between_pings", DEFAULT_MIN_DAYS)

    log_file = os.path.join(
        PA_LOG_DIR, f"pa_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
    )

    def log(msg, level="INFO"):
        ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"{ts} | {level:8s} | {msg}"
        print(line, flush=True)
        with open(log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    log("=" * 60)
    log("PING AGAIN (--pa) started")
    log(f"Max conversations: {max_conversations}, Min days between pings: {min_days}")
    log("=" * 60)

    # Navigate to messaging
    log("Navigating to LinkedIn Messaging...")
    driver.get(MESSAGING_URL)
    random_delay(3, 5)

    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR,
                "li.msg-conversation-listitem, li.msg-conversations-container__convo-item"
            ))
        )
    except TimeoutException:
        log("Could not load messaging page or no conversations found.", "ERROR")
        return

    log("Messaging page loaded. Scrolling to find eligible conversations...")
    start_index, total_loaded = _scroll_until_old_enough(min_days, max_conversations)
    log(f"Starting from conversation index {start_index} (total loaded: {total_loaded}).")

    if total_loaded == 0:
        log("No conversations loaded.", "WARN")
        return

    # Read sidebar timestamps to know which ones to skip without clicking
    sidebar_ts_list = _get_sidebar_timestamps()
    now = datetime.now()

    conv_items = _get_conversation_items(max_conversations)
    total = len(conv_items)
    log(f"Processing conversations from index {start_index} to {total - 1}.")

    pinged = 0
    skipped = 0
    skipped_recent = 0
    errors = 0

    for i in range(start_index, total):
        try:
            # Re-fetch items each iteration (DOM refreshes)
            conv_items = _get_conversation_items(max_conversations)
            if i >= len(conv_items):
                log(f"Index {i} out of range after DOM refresh, stopping.", "WARN")
                break

            conv = conv_items[i]
            person_name = _get_person_name_from_conversation_item(conv) or f"Person #{i+1}"

            log(f"[{i+1}/{total}] Processing: {person_name}")

            # Quick pre-check: sidebar timestamp — skip if too recent
            if i < len(sidebar_ts_list):
                sidebar_text = sidebar_ts_list[i].get("text", "")
                sidebar_dt = None
                try:
                    sidebar_dt = datetime.fromisoformat(
                        sidebar_text.replace("Z", "+00:00")
                    ).replace(tzinfo=None)
                except (ValueError, AttributeError):
                    sidebar_dt = _parse_linkedin_date(sidebar_text)
                if sidebar_dt:
                    sidebar_days = (now - sidebar_dt).days
                    if sidebar_days < min_days:
                        log(f"  SKIP (sidebar): {sidebar_text!r} = {sidebar_days}d ago (need >= {min_days}).")
                        skipped_recent += 1
                        continue
                    else:
                        log(f"  Sidebar: {sidebar_text!r} = {sidebar_days}d ago — eligible window.")

            # Quick pre-check via sidebar preview
            preview_is_me, preview_text = _conversation_preview_starts_with_you(conv)
            if preview_is_me is False:
                log(f"  SKIP: Preview indicates last message not by us.")
                skipped += 1
                continue

            # Click on the conversation
            try:
                conv.click()
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", conv)
            random_delay(1.5, 2.5)

            # Read last message
            sender_is_me, message_text, parsed_ts = _get_last_message_info()

            if message_text is None:
                log(f"  Could not read last message. Skipping.", "WARN")
                skipped += 1
                continue

            # --- Debug info ---
            short_preview = message_text[:120] + ("..." if len(message_text) > 120 else "")
            sender_label = "ME" if sender_is_me else "THEM"
            ts_str = parsed_ts.strftime('%Y-%m-%d %H:%M') if parsed_ts else "UNKNOWN"
            if parsed_ts:
                delta = datetime.now() - parsed_ts
                days = delta.days
                hours, remainder = divmod(delta.seconds, 3600)
                mins = remainder // 60
                delta_str = f"{days}d {hours}h {mins}m ago"
            else:
                delta_str = "UNKNOWN"
            log(f"  ┌─ DEBUG ──────────────────────────────────")
            log(f"  │ Sender   : {sender_label}")
            log(f"  │ Time     : {ts_str}")
            log(f"  │ Delta    : {delta_str}")
            log(f"  │ Message  : \"{short_preview}\"")
            log(f"  └───────────────────────────────────────────")

            # Condition 1: sent by us
            if not sender_is_me:
                log(f"  SKIP: Last message was not sent by us.")
                skipped += 1
                continue

            # Condition 2: starts with Hello
            if not "years" in message_text.lower():
                log(f"  SKIP: Last message does not contain with 'years'.")
                skipped += 1
                continue

            # Condition 3: last message must be older than min_days
            if parsed_ts is None:
                log(f"  SKIP: Could not parse timestamp — skipping to be safe.", "WARN")
                skipped += 1
                continue

            days_ago = (datetime.now() - parsed_ts).days
            if days_ago < min_days:
                log(f"  SKIP: Last message was {days_ago} day(s) ago (need >= {min_days}).")
                skipped += 1
                continue
            log(f"  Eligible: last message was {days_ago} day(s) ago.")

            # Send ping again
            log(f"  Sending ping-again message...")
            if _send_message(CONNECTION_NOTE):
                pinged += 1
                log(f"  ✓ Message sent to {person_name}.")
            else:
                errors += 1
                log(f"  ✗ Failed to send to {person_name}.", "ERROR")

            random_delay(1, 2)

        except (StaleElementReferenceException, NoSuchElementException) as e:
            log(f"  Error on conversation {i+1}: {type(e).__name__}: {e}", "ERROR")
            errors += 1
        except Exception as e:
            log(f"  Unexpected error on conversation {i+1}: {type(e).__name__}: {e}", "ERROR")
            errors += 1

    log("=" * 60)
    log(f"PING AGAIN done. Pinged: {pinged}, Skipped (recent): {skipped_recent}, Skipped (other): {skipped}, Errors: {errors}")
    log(f"Log file: {log_file}")
    log("=" * 60)
