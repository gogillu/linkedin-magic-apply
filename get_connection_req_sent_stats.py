import csv
import os
import glob
import argparse
from collections import defaultdict
from datetime import datetime, timedelta

LOG_DIR = os.path.join(os.path.dirname(__file__), "linkedin/log")
STATS_DIR = os.path.join(os.path.dirname(__file__), "statistics")
STATS_FILE = os.path.join(STATS_DIR, "statistics.csv")


def parse_logs(show_all=False):
    """Parse all CSV files in log/ and return per-company, per-date send counts."""
    # { company: { date_str: count } }
    stats = defaultdict(lambda: defaultdict(int))
    cutoff_date = None if show_all else (datetime.now() - timedelta(days=30)).strftime("%Y-%m-%d")

    log_files = glob.glob(os.path.join(LOG_DIR, "*.csv"))
    if not log_files:
        print("[!] No log files found in log/ directory.")
        return stats

    for filepath in log_files:
        with open(filepath, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                status = row.get("status", "").strip().lower()
                if status != "sent":
                    continue
                company = row.get("company", "Unknown").strip()
                timestamp = row.get("timestamp", "").strip()
                # Extract date part (YYYY-MM-DD) from timestamp
                date_str = timestamp[:10] if len(timestamp) >= 10 else "unknown"

                # Filter out records older than 1 month unless --all
                if cutoff_date and date_str != "unknown" and date_str < cutoff_date:
                    continue

                stats[company][date_str] += 1

    return stats


def write_statistics(stats):
    """Write aggregated statistics to statistics/statistics.csv."""
    os.makedirs(STATS_DIR, exist_ok=True)

    with open(STATS_FILE, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["company", "total_sent", "date_breakdown"])

        for company in sorted(stats.keys()):
            date_counts = stats[company]
            total = sum(date_counts.values())
            breakdown = " | ".join(
                f"{date}={count}" for date, count in sorted(date_counts.items())
            )
            writer.writerow([company, total, breakdown])

    print(f"[✓] Statistics written to {STATS_FILE}")


def get_daily_totals(stats):
    """Aggregate total connection requests sent per day across all companies."""
    daily = defaultdict(int)
    for company, date_counts in stats.items():
        for date_str, count in date_counts.items():
            daily[date_str] += count
    return daily


def get_weekly_breakdown(stats):
    """Aggregate per-company counts grouped by week (Monday start).
    Returns: { week_label: { company: count } } ordered dict-friendly structure.
    """
    # { (week_start_date): { company: count } }
    weekly = defaultdict(lambda: defaultdict(int))

    for company, date_counts in stats.items():
        for date_str, count in date_counts.items():
            try:
                dt = datetime.strptime(date_str, "%Y-%m-%d")
                # Monday of that week
                week_start = dt - timedelta(days=dt.weekday())
                weekly[week_start][company] += count
            except ValueError:
                # Handle "unknown" or malformed dates
                week_start = None
                weekly[week_start][company] += count

    return weekly


def main():
    parser = argparse.ArgumentParser(description="Connection request sent statistics.")
    parser.add_argument(
        "--all",
        action="store_true",
        help="Show all stats (including records older than 1 month)",
    )
    args = parser.parse_args()

    stats = parse_logs(show_all=args.all)
    if not stats:
        print("[!] No successful connection requests found in logs.")
        return
    write_statistics(stats)

    grand_total = 0

    # Table 1: Per-company breakdown
    print(f"\n{'='*80}")
    print("TABLE 1: Connection Requests Sent Per Company")
    print(f"{'='*80}")
    print(f"{'Company':<30} {'Total':<8} {'Date Breakdown'}")
    print("-" * 80)
    for company in sorted(stats.keys()):
        date_counts = stats[company]
        total = sum(date_counts.values())
        grand_total += total
        breakdown = " | ".join(
            f"{d}={c}" for d, c in sorted(date_counts.items())
        )
        print(f"{company:<30} {total:<8} {breakdown}")

    # Table 2: Per-day breakdown
    daily_totals = get_daily_totals(stats)
    print(f"\n{'='*80}")
    print("TABLE 2: Connection Requests Sent Per Day")
    print(f"{'='*80}")
    print(f"{'Date':<20} {'Total Sent':<10}")
    print("-" * 40)
    for date_str in sorted(daily_totals.keys()):
        print(f"{date_str:<20} {daily_totals[date_str]:<10}")

    # Table 3: Per-week breakdown with company details
    weekly_breakdown = get_weekly_breakdown(stats)
    print(f"\n{'='*100}")
    print("TABLE 3: Connection Requests Sent Per Week")
    print(f"{'='*100}")
    print(f"{'Week (Mon-Sun)':<25} {'Total':<8} {'Company Breakdown'}")
    print("-" * 100)

    for week_start in sorted(k for k in weekly_breakdown.keys() if k is not None):
        week_end = week_start + timedelta(days=6)
        week_label = f"{week_start.strftime('%Y-%m-%d')} to {week_end.strftime('%Y-%m-%d')}"
        company_counts = weekly_breakdown[week_start]
        week_total = sum(company_counts.values())
        company_detail = ", ".join(
            f"{comp}={cnt}" for comp, cnt in sorted(company_counts.items(), key=lambda x: -x[1])
        )
        print(f"{week_label:<25} {week_total:<8} {company_detail}")

    # Handle unknown dates if any
    if None in weekly_breakdown:
        company_counts = weekly_breakdown[None]
        week_total = sum(company_counts.values())
        company_detail = ", ".join(
            f"{comp}={cnt}" for comp, cnt in sorted(company_counts.items(), key=lambda x: -x[1])
        )
        print(f"{'Unknown':<25} {week_total:<8} {company_detail}")

    # Grand total
    print(f"\n{'='*80}")
    if not args.all:
        print(f"TOTAL (last 30 days): {grand_total} connection requests sent")
    else:
        print(f"TOTAL (all time): {grand_total} connection requests sent")
    print(f"{'='*80}")


if __name__ == "__main__":
    main()