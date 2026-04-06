import json
import urllib.parse
import os

CREDENTIAL_FILE = "linkedin/credential.json"
COMPANIES_FILE = "companies.txt"
COMPANIES_OLD_FILE = "companies_old.txt"
CONNECTION_NOTE_FILE = "connection_note.txt"
MAX_PAGES = 5
MAX_REQUESTS_PER_COMPANY = 3
DELAY_BETWEEN_ACTIONS = (2, 4)

def log(message):
    """Print a message and flush immediately so it appears in real time."""
    print(message, flush=True)

def load_companies(filepath=COMPANIES_FILE):
    """Read company names from a text file, one per line.
    Supports optional comma-separated request count, e.g. 'Microsoft,25'.
    Returns a list of (company_name, max_requests) tuples.
    """
    companies = []
    with open(filepath, "r") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            if "," in line:
                parts = line.split(",", 1)
                name = parts[0].strip()
                try:
                    count = int(parts[1].strip())
                except ValueError:
                    count = MAX_REQUESTS_PER_COMPANY
            else:
                name = line
                count = MAX_REQUESTS_PER_COMPANY
            companies.append((name, count))
    return companies

def decrement_company_count(company_name, sent_count, filepath=COMPANIES_FILE):
    """Decrement the remaining count for a company in companies.txt by sent_count.
    Removes the company line if count drops to 0 or below.
    """
    if sent_count <= 0:
        return

    lines = []
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    new_lines = []
    for line in lines:
        stripped = line.strip()
        if not stripped:
            new_lines.append(line)
            continue
        if "," in stripped:
            parts = stripped.split(",", 1)
            name = parts[0].strip()
            try:
                count = int(parts[1].strip())
            except ValueError:
                new_lines.append(line)
                continue
            if name == company_name:
                count -= sent_count
                if count > 0:
                    new_lines.append(f"{name},{count}\n")
                # else: drop the line (company fully processed)
            else:
                new_lines.append(line)
        else:
            name = stripped
            if name == company_name:
                # No count specified, treat as MAX_REQUESTS_PER_COMPANY
                remaining = MAX_REQUESTS_PER_COMPANY - sent_count
                if remaining > 0:
                    new_lines.append(f"{name},{remaining}\n")
                # else: drop
            else:
                new_lines.append(line)

    with open(filepath, "w", encoding="utf-8") as f:
        f.writelines(new_lines)


def update_companies_old(company_name, sent_count, filepath=COMPANIES_OLD_FILE):
    """Add/update the total sent count for a company in companies_old.txt.
    Each company appears only once. Counts are accumulated across runs.
    """
    if sent_count <= 0:
        return

    # Read existing entries
    existing = {}  # { company_name: total_sent }
    if os.path.isfile(filepath):
        with open(filepath, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if not stripped:
                    continue
                if "," in stripped:
                    parts = stripped.split(",", 1)
                    name = parts[0].strip()
                    try:
                        count = int(parts[1].strip())
                    except ValueError:
                        count = 0
                    existing[name] = count
                else:
                    existing[stripped] = 0

    # Accumulate
    existing[company_name] = existing.get(company_name, 0) + sent_count

    # Write back (sorted for readability)
    with open(filepath, "w", encoding="utf-8") as f:
        for name in sorted(existing.keys()):
            f.write(f"{name},{existing[name]}\n")


def build_search_url(company_name):
    """Build a LinkedIn people search URL for the given company."""
    encoded = urllib.parse.quote(company_name)
    return f"https://www.linkedin.com/search/results/people/?keywords=talent%20acquisition%20{encoded}&origin=GLOBAL_SEARCH_HEADER"

with open(CREDENTIAL_FILE, "r") as f:
    creds = json.load(f)
EMAIL = creds["email"]
PASSWORD = creds["password"]

with open(CONNECTION_NOTE_FILE, "r", encoding="utf-8") as f:
    CONNECTION_NOTE = f.read().strip()

if len(CONNECTION_NOTE) > 300:
    print("[!] Connection note exceeds 300 chars – LinkedIn may reject it. Truncating.")
    CONNECTION_NOTE = CONNECTION_NOTE[:300]