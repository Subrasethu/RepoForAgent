# ─────────────────────────────────────────────────
# main.py
# Master controller — runs the full agent pipeline
# from CSV ingestion to approval dashboard
#
# HOW TO RUN:
# 1. Make sure Ollama is running
# 2. Press F5 in Spyder or run:
#    python main.py
# ─────────────────────────────────────────────────

import os
import sys
from datetime import datetime

# Auto detect project root
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

from ticketrepoagent.ingest      import (
    load_config,
    load_tickets,
    clean_tickets
)
from ticketrepoagent.embedder    import (
    load_model,
    generate_embeddings,
    load_embeddings,
    save_embeddings
)
from ticketrepoagent.similarity  import process_new_tickets
from ticketrepoagent.repo        import (
    load_master_repo,
    get_active_issues,
    get_master_repo_summary
)
from ui.approval_ui              import run_approval_ui


def print_banner():
    """Prints a welcome banner when agent starts"""
    print("=" * 55)
    print("   AMS Knowledge Agent — Teamcenter AMS Project")
    print("=" * 55)
    print(f"   Run started : {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 55)


def check_ollama(config):
    """
    Checks if Ollama is running before starting.
    Gives a clear message if not running.
    """
    import requests
    ollama_url = config["embedding"]["ollama_url"]
    try:
        response = requests.get(
            f"{ollama_url}/api/tags",
            timeout=5
        )
        if response.status_code == 200:
            print("Ollama         : Running")
            return True
        else:
            print("Ollama         : Not responding!")
            return False
    except Exception:
        print("\nERROR: Ollama is not running!")
        print("Please start Ollama first then run again.")
        print("Open WinPython Command Prompt and run:")
        print("   ollama serve")
        return False


def run_agent():
    """
    Main agent pipeline — runs all steps in order.
    """
    print_banner()

    # ── Step 1: Load config ───────────────────────
    print("\n── Step 1: Loading Configuration ────────")
    config = load_config()
    print(f"Threshold      : {config['similarity']['threshold']}")
    print(f"Embedding model: {config['embedding']['model_name']}")
    print(f"Input folder   : {config['paths']['input_folder']}")

    # ── Step 2: Check Ollama ──────────────────────
    print("\n── Step 2: Checking Ollama ───────────────")
    if not check_ollama(config):
        return

    # ── Step 3: Load tickets from CSV ────────────
    print("\n── Step 3: Loading Tickets from CSV ──────")
    tickets = load_tickets(config)

    if tickets.empty:
        print("No tickets found in input folder!")
        print(f"Please add CSV files to:")
        print(f"{config['paths']['input_folder']}")
        return

    tickets = clean_tickets(tickets, config)

    # ── Step 4: Load master repo ──────────────────
    print("\n── Step 4: Loading Master Repository ────")
    active_issues = get_active_issues(config)
    print(f"Active issues in master repo: {len(active_issues)}")

    # ── Step 5: Load or generate embeddings ──────
    print("\n── Step 5: Loading Embeddings ────────────")
    master_embeddings, master_ids = load_embeddings(config)

    if master_embeddings is None or len(master_ids) == 0:
        print("No embeddings found!")
        print("Generating embeddings for all tickets...")
        model_config      = load_model(config)
        master_embeddings = generate_embeddings(
            tickets, model_config
        )
        master_ids        = tickets["ticket_id"].tolist()
        save_embeddings(
            master_embeddings,
            master_ids,
            config
        )
        print("Embeddings generated and saved!")
        print("Please run agent again to process new tickets.")
        return
    else:
        print(f"Loaded {len(master_ids)} existing embeddings")

    # ── Step 6: Find new tickets ──────────────────
    print("\n── Step 6: Finding New Tickets ───────────")

    # Get ticket IDs already in master repo
    master_df      = load_master_repo(config)
    existing_ids   = (
        master_df["issue_id"].tolist()
        if not master_df.empty
        else []
    )

    # Filter to only truly new tickets
    # not yet in master repo at all
    truly_new = tickets[
        ~tickets["ticket_id"].isin(existing_ids)
    ]

    print(f"Total tickets in CSV    : {len(tickets)}")
    print(f"Already in master repo  : {len(existing_ids)}")
    print(f"New tickets to check    : {len(truly_new)}")

    if truly_new.empty:
        print("\nAll tickets already processed!")
        print("Add new CSV files to data/input and run again.")
        get_master_repo_summary(config)
        return

    # ── Step 7: Generate embeddings for new tickets
    print("\n── Step 7: Generating New Embeddings ─────")
    model_config   = load_model(config)
    new_embeddings = generate_embeddings(
        truly_new, model_config
    )

    # ── Step 8: Similarity check ──────────────────
    print("\n── Step 8: Running Similarity Check ──────")
    known_issues, new_issues = process_new_tickets(
        truly_new,
        new_embeddings,
        master_embeddings,
        master_ids,
        config
    )

    # ── Step 9: Summary before UI ────────────────
    print("\n── Step 9: Agent Decision Summary ────────")
    print(f"Known issues (skipped)  : {len(known_issues)}")
    print(f"New issues (for review) : {len(new_issues)}")

    if known_issues:
        print("\nKnown issues detected:")
        for k in known_issues:
            print(f"  {k['ticket_id']} matched "
                  f"{k['best_match_id']} "
                  f"(score: {k['best_score']})")

    # ── Step 10: Launch approval UI ───────────────
    if not new_issues:
        print("\nNo new issues to review!")
        print("All tickets are known issues.")
        get_master_repo_summary(config)
        return

    print(f"\n── Step 10: Launching Approval Dashboard ─")
    print(f"Opening browser at http://localhost:5006")
    print(f"Review {len(new_issues)} new issue(s) "
          f"in the dashboard...")
    print(f"\nPress Ctrl+C to stop the dashboard "
          f"when done reviewing.\n")

    approved, rejected = run_approval_ui(
        new_issues     = new_issues,
        new_tickets_df = truly_new,
        new_embeddings = new_embeddings,
        config         = config
    )

    # ── Step 11: Final summary ────────────────────
    print("\n── Step 11: Session Complete ─────────────")
    print(f"Approved this session : {len(approved)}")
    print(f"Rejected this session : {len(rejected)}")
    get_master_repo_summary(config)
    print("\n" + "=" * 55)
    print("   Agent run complete!")
    print("=" * 55)


if __name__ == "__main__":
    run_agent()
