import argparse
from linkedin.main import main as linkedin_main, pa_main as linkedin_pa_main

def main():
    parser = argparse.ArgumentParser(description="Automate connection requests.")
    parser.add_argument(
        "--applicationPortal",
        type=str,
        choices=["linkedin", "instahyre"],
        default="linkedin",
        help="Portal to use: linkedin or instahyre (default: linkedin)"
    )
    parser.add_argument(
        "--pa",
        action="store_true",
        help="Ping Again: re-send messages to people whose last message was sent by you, starts with 'Hello', and is older than 2 days"
    )
    args = parser.parse_args()

    if args.pa:
        linkedin_pa_main()
    elif args.applicationPortal == "instahyre":
        from instahyre.instahyre_apply import apply_to_jobs
        apply_to_jobs()
    else:
        linkedin_main()

if __name__ == "__main__":
    main()