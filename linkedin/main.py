from linkedin.config import MAX_PAGES, MAX_REQUESTS_PER_COMPANY, load_companies, build_search_url, decrement_company_count, update_companies_old
from linkedin.browser import driver
from linkedin.auth import login
from linkedin.utils import random_delay, dismiss_any_modal, scroll_to_bottom
from linkedin.connect import send_connection_requests_on_page, go_to_next_page
from linkedin.ping_again import ping_again
import csv
import os
from datetime import datetime


LOG_DIR = os.path.join(os.path.dirname(__file__), "log")
os.makedirs(LOG_DIR, exist_ok=True)

LOG_FILE = os.path.join(
    LOG_DIR, f"connection_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
)
CSV_HEADERS = ["timestamp", "company", "person_name", "method", "note", "status", "page", "page_url"]


def write_log_entry(entry, company, page):
    """Append a single log entry to the CSV file immediately."""
    file_exists = os.path.isfile(LOG_FILE) and os.path.getsize(LOG_FILE) > 0
    with open(LOG_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_HEADERS)
        if not file_exists:
            writer.writeheader()
        writer.writerow({
            "timestamp": entry["timestamp"],
            "company": company,
            "person_name": entry["person_name"],
            "method": entry["method"],
            "note": entry["note"],
            "status": entry["status"],
            "page": page,
            "page_url": entry["page_url"],
        })


def main():
    total_sent = 0
    try:
        login()

        companies = load_companies("companies.txt")
        for company, max_requests in companies:
            search_url = build_search_url(company)
            print(f"\n{'='*60}")
            print(f"Processing company: {company}")
            print(f"URL: {search_url}")
            print(f"Max requests: {max_requests}")
            print(f"{'='*60}")

            driver.get(search_url)
            random_delay(1, 2)

            company_sent = 0
            page = 1
            while company_sent < max_requests:
                remaining = max_requests - company_sent
                print(f"\n— Page {page} for '{company}' (remaining: {remaining}) —", flush=True)

                log_callback = lambda entry: write_log_entry(entry, company, page)
                sent, log_entries = send_connection_requests_on_page(remaining=remaining, max_req_to_people=remaining, log_callback=log_callback)
                company_sent += sent
                total_sent += sent

                # Decrement companies.txt and update companies_old.txt after each page
                if sent > 0:
                    decrement_company_count(company, sent)
                    update_companies_old(company, sent)
                    print(f"  [✓] Updated companies.txt (-{sent}) and companies_old.txt (+{sent}) for '{company}'", flush=True)

                print(f"  Sent {sent} connection(s) on this page. (Company total: {company_sent})", flush=True)

                if company_sent >= max_requests:
                    print(f"  Reached max {max_requests} for '{company}', moving on.", flush=True)
                    break
                if not go_to_next_page():
                    print("  No more pages.", flush=True)
                    break
                page += 1

    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.", flush=True)
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}", flush=True)
    finally:
        print(f"\n[✓] Done. Total connection requests sent: {total_sent}", flush=True)
        print(f"    Log file: {LOG_FILE}", flush=True)
        input("Press ENTER to close the browser …")
        driver.quit()


if __name__ == "__main__":
    main()


def pa_main():
    """Login, then run the Ping Again flow."""
    try:
        login()
        ping_again()
    except KeyboardInterrupt:
        print("\n[!] Interrupted by user.", flush=True)
    except Exception as e:
        print(f"\n[!] Unexpected error: {e}", flush=True)
    finally:
        input("Press ENTER to close the browser …")
        driver.quit()