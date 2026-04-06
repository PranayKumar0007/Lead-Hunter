"""
tracker_cli.py — Command-line tool to view and manage the Lead Hunter database
================================================================================
Usage:
  python tracker_cli.py                                  # show all leads
  python tracker_cli.py --status follow_up_1             # filter by status
  python tracker_cli.py --due                            # show leads due for follow-up TODAY
  python tracker_cli.py --mark domain.com replied        # mark reply received
  python tracker_cli.py --mark domain.com booked         # mark call booked
  python tracker_cli.py --mark domain.com dead           # remove from sequence
  python tracker_cli.py --update domain.com sent         # update a lead's status (any status)
  python tracker_cli.py --summary                        # print stats only
"""

import sys
from lead_tracker import load_db, update_status, get_summary, get_leads_due_for_followup

VALID_STATUSES = {
    "pending", "sent",
    "follow_up_1", "follow_up_2", "follow_up_3",
    "closing", "replied", "booked", "closed", "dead", "skipped",
}

STATUS_ICONS = {
    "pending":      "⏳",
    "sent":         "✅",
    "follow_up_1":  "📨",
    "follow_up_2":  "📨📨",
    "follow_up_3":  "📨📨📨",
    "closing":      "📞",
    "replied":      "💬",
    "booked":       "🎉",
    "closed":       "💰",
    "dead":         "⚰️ ",
    "skipped":      "⏭️ ",
}


def print_leads(db: dict, filter_status: str = None) -> None:
    """Print leads as a formatted table, optionally filtered by status."""
    rows = [
        (domain, r) for domain, r in db.items()
        if filter_status is None or r.get("outreach_status") == filter_status
    ]

    if not rows:
        status_label = f"status='{filter_status}'" if filter_status else "any status"
        print(f"  No leads found with {status_label}.")
        return

    print(f"\n{'#':<4} {'Company':<35} {'Email':<35} {'Status':<12} {'Last Contacted'}")
    print("-" * 105)
    for i, (domain, r) in enumerate(rows, 1):
        status = r.get("outreach_status", "pending")
        icon = STATUS_ICONS.get(status, "")
        name = r.get("name", domain)[:33]
        email = r.get("email", "")[:33]
        contacted = r.get("last_contacted") or "never"
        print(f"{i:<4} {name:<35} {email:<35} {icon} {status:<10} {contacted}")

    print(f"\n  {len(rows)} lead(s) shown.\n")


def main():
    args = sys.argv[1:]

    # --mark domain.com <status>  (alias for --update, for outcome statuses)
    if "--mark" in args:
        idx = args.index("--mark")
        if idx + 2 >= len(args):
            print("Usage: python tracker_cli.py --mark <domain> <status>")
            print(f"Valid statuses: {sorted(VALID_STATUSES)}")
            sys.exit(1)
        domain     = args[idx + 1]
        new_status = args[idx + 2]
        update_status(domain, new_status)
        return

    # --update domain.com <status>  (backward-compatible)
    if "--update" in args:
        idx = args.index("--update")
        if idx + 2 >= len(args):
            print("Usage: python tracker_cli.py --update <domain> <status>")
            print(f"Valid statuses: {sorted(VALID_STATUSES)}")
            sys.exit(1)
        domain     = args[idx + 1]
        new_status = args[idx + 2]
        update_status(domain, new_status)
        return

    db = load_db()
    if not db:
        print("No leads in the database yet. Run the pipeline first.")
        return

    # --due: show leads due for follow-up today
    if "--due" in args:
        due = get_leads_due_for_followup()
        if not due:
            print("\n  ✅ No leads are due for follow-up today.\n")
        else:
            from follow_up_writer import STEP_LABELS
            print(f"\n  📬 {len(due)} lead(s) due for follow-up today:\n")
            print(f"  {'#':<4} {'Company':<35} {'Email':<35} {'Step':<12} Last Contacted")
            print("  " + "-" * 100)
            for i, (domain, r, step) in enumerate(due, 1):
                name      = r.get("name", domain)[:33]
                email     = r.get("email", "")[:33]
                step_lbl  = STEP_LABELS.get(step, f"Step {step}")
                contacted = r.get("last_contacted") or "never"
                print(f"  {i:<4} {name:<35} {email:<35} {step_lbl:<25} {contacted}")
            print()
        return

    # --summary only
    if "--summary" in args:
        get_summary(db)
        return

    # --status <filter>
    filter_status = None
    if "--status" in args:
        idx = args.index("--status")
        if idx + 1 < len(args):
            filter_status = args[idx + 1]
            if filter_status not in VALID_STATUSES:
                print(f"Invalid status '{filter_status}'. Valid options: {sorted(VALID_STATUSES)}")
                sys.exit(1)

    # Default: show all leads as table + summary
    print_leads(db, filter_status)
    if filter_status is None:
        get_summary(db)


if __name__ == "__main__":
    main()
