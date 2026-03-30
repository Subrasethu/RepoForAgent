import os
import numpy as np
import pandas as pd
from datetime import datetime

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ── Valid values come from config.yaml ───────────
# These are set dynamically when config is loaded
# Default fallback values kept here for safety
VALIDITY_ACTIVE   = "Active"
VALIDITY_OBSOLETE = "Obsolete"

def validate_validity(validity_value, config):
    """
    Checks if a validity value is allowed.
    Allowed values come from config.yaml:
    validity_options: Active, Obsolete, Under Review

    Returns True if valid, False if not.
    """
    allowed = config.get("approval", {}).get(
        "validity_options",
        ["Active", "Obsolete", "Under Review"]
    )

    if validity_value in allowed:
        return True
    else:
        print(f"Invalid validity value: '{validity_value}'")
        print(f"Allowed values: {allowed}")
        return False

def get_paths(config):
    """
    Returns all important file paths
    built from config settings.
    """
    base       = config["BASE_DIR"]
    output_dir = os.path.join(base, config["paths"]["output_folder"])
    return {
        "output_dir"  : output_dir,
        "master_repo" : os.path.join(base, config["paths"]["master_repo"]),
        "embeddings"  : os.path.join(output_dir, "embeddings.npy"),
        "ticket_ids"  : os.path.join(output_dir, "ticket_ids.npy"),
    }


def load_master_repo(config):
    """
    Loads the master Excel repository.
    If it does not exist yet creates an empty one
    with all columns including new ones.
    """
    paths = get_paths(config)
    os.makedirs(paths["output_dir"], exist_ok=True)

    if os.path.exists(paths["master_repo"]):
        df = pd.read_excel(paths["master_repo"])
        print(f"Master repo loaded: {len(df)} existing issues")
        return df
    else:
        print("Master repo not found - creating new one...")
        df = pd.DataFrame(columns=[
            # ── Core ticket fields ──────────────
            "issue_id",
            "source",
            "issue_text",
            "resolution",
            "category",
            "priority",
            # ── Approval fields ─────────────────
            "approver_id",
            "approver_name",
            "approved_at",
            "status",
            # ── SOP reference ───────────────────
            "sop_reference",
            # ── Validity fields ─────────────────
            "validity",
            "validity_updated_by",
            "validity_updated_at",
            "obsolete_reason",
            # ── Agent metadata ──────────────────
            "similarity_at_detection",
        ])
        save_master_repo(df, config)
        print("New master repo created!")
        return df


def save_master_repo(df, config):
    """
    Saves the master DataFrame to Excel file.
    """
    paths = get_paths(config)
    os.makedirs(paths["output_dir"], exist_ok=True)
    df.to_excel(paths["master_repo"], index=False)
    print(f"Master repo saved: {len(df)} issues")


def issue_exists(ticket_id, master_df):
    """
    Checks if a ticket ID already exists
    in the master repo.
    Prevents duplicate entries.
    """
    if master_df.empty:
        return False
    return ticket_id in master_df["issue_id"].values


def append_approved_issue(ticket, decision, approver_id,
                          approver_name, config,
                          sop_reference=None):
    """
    Adds a newly approved issue to the master repo.

    ticket        = full ticket row from CSV
    decision      = similarity decision dictionary
    approver_id   = employee/user ID of approver
    approver_name = full name of SME or approver
    config        = project config
    sop_reference = optional SOP document number
                    e.g. 'SOP-TC-2025-042'
                    Leave empty if not available
    """
    paths     = get_paths(config)
    master_df = load_master_repo(config)
    ticket_id = decision["ticket_id"]

    # Check if already exists - prevent duplicates
    if issue_exists(ticket_id, master_df):
        print(f"Ticket {ticket_id} already in master repo!")
        return master_df

    # Build new row with all columns
    new_row = {
        # ── Core ticket fields ──────────────────
        "issue_id"               : ticket_id,
        "source"   : ticket.get(
                  "source",
                  config.get("master_repo", {}).get("source_default", "CSV")
              ),
        "issue_text"             : ticket.get("description", ""),
        "resolution"             : ticket.get("resolution", ""),
        "category"               : ticket.get("category", ""),
        "priority"               : ticket.get("priority", ""),
        # ── Approval fields ─────────────────────
        "approver_id"            : approver_id,
        "approver_name"          : approver_name,
        "approved_at"            : datetime.now().strftime(
                                       "%Y-%m-%d %H:%M:%S"),
        "status"                 : "Validated",
        # ── SOP reference ────────────────────────
        # If no SOP available stores empty string
        "sop_reference"          : sop_reference if sop_reference else "",
        # ── Validity fields ──────────────────────
        # Default is Active when first approved
        "validity" : config.get("approval", {}).get(
                 "default_validity", VALIDITY_ACTIVE
             ),
        "validity_updated_by"    : "",
        "validity_updated_at"    : "",
        "obsolete_reason"        : "",
        # ── Agent metadata ───────────────────────
        "similarity_at_detection": decision["best_score"],
    }

    # Add new row to DataFrame
    new_row_df = pd.DataFrame([new_row])
    master_df  = pd.concat([master_df, new_row_df], ignore_index=True)

    # Save updated master repo
    save_master_repo(master_df, config)
    print(f"Ticket {ticket_id} added by {approver_name} "
          f"(ID: {approver_id})")
    if sop_reference:
        print(f"SOP reference tagged: {sop_reference}")

    return master_df


def mark_obsolete(ticket_id, updated_by_id,
                  updated_by_name, reason, config,
                  new_validity=None):
    """
    Marks an existing issue as Obsolete or Under Review.

    new_validity defaults to Obsolete if not specified.
    Can also be set to Under Review from config options.
    """
    master_df = load_master_repo(config)

    # Use Obsolete as default if not specified
    if new_validity is None:
        new_validity = VALIDITY_OBSOLETE

    # Validate against allowed values in config
    if not validate_validity(new_validity, config):
        print("Validity update cancelled - invalid value!")
        return master_df

    if not issue_exists(ticket_id, master_df):
        print(f"Ticket {ticket_id} not found!")
        return master_df

    idx = master_df.index[
        master_df["issue_id"] == ticket_id
    ].tolist()[0]

    master_df.at[idx, "validity"]            = new_validity
    master_df.at[idx, "validity_updated_by"] = (
        f"{updated_by_name} ({updated_by_id})"
    )
    master_df.at[idx, "validity_updated_at"] = (
        datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    )
    master_df.at[idx, "obsolete_reason"]     = reason
    master_df.at[idx, "status"]              = new_validity

    save_master_repo(master_df, config)
    print(f"Ticket {ticket_id} marked as {new_validity}")
    print(f"Reason    : {reason}")
    print(f"Updated by: {updated_by_name} ({updated_by_id})")

    return master_df


def update_sop_reference(ticket_id, sop_reference,
                         updated_by_name, config):
    """
    Updates or adds SOP reference to an existing issue.
    SME can tag a SOP document at any time after approval.
    """
    master_df = load_master_repo(config)

    if not issue_exists(ticket_id, master_df):
        print(f"Ticket {ticket_id} not found!")
        return master_df

    idx = master_df.index[
        master_df["issue_id"] == ticket_id
    ].tolist()[0]

    old_sop = master_df.at[idx, "sop_reference"]
    master_df.at[idx, "sop_reference"] = sop_reference

    save_master_repo(master_df, config)
    print(f"SOP reference updated for {ticket_id}")
    print(f"Old SOP : {old_sop}")
    print(f"New SOP : {sop_reference}")
    print(f"Updated by: {updated_by_name}")

    return master_df


def get_active_issues(config):
    """
    Returns only Active issues from master repo.
    These are used for similarity comparison —
    Obsolete issues are excluded automatically!
    """
    master_df = load_master_repo(config)

    if master_df.empty:
        return master_df

    active_df = master_df[
        master_df["validity"] == VALIDITY_ACTIVE
    ]
    print(f"Active issues   : {len(active_df)}")
    print(f"Obsolete issues : {len(master_df) - len(active_df)}")
    return active_df


def get_master_repo_summary(config):
    """
    Prints a full summary of the master repo.
    """
    master_df = load_master_repo(config)

    if master_df.empty:
        print("Master repo is empty!")
        return

    active_count   = len(
        master_df[master_df["validity"] == VALIDITY_ACTIVE]
    )
    obsolete_count = len(
        master_df[master_df["validity"] == VALIDITY_OBSOLETE]
    )
    sop_count      = len(
        master_df[master_df["sop_reference"] != ""]
    )

    print("\n── Master Repo Summary ──────────────────")
    print(f"Total issues     : {len(master_df)}")
    print(f"Active           : {active_count}")
    print(f"Obsolete         : {obsolete_count}")
    print(f"With SOP ref     : {sop_count}")
    print(f"Sources          : {master_df['source'].unique()}")
    if not master_df.empty:
        print(f"\nRecent issues:")
        cols = ["issue_id", "approver_name",
                "sop_reference", "validity", "approved_at"]
        print(master_df[cols].tail(5).to_string())


def append_embedding(new_embedding, new_ticket_id, config):
    """
    Appends a single new embedding to the index.
    Called after every approved issue.
    Never recomputes existing embeddings!
    """
    paths = get_paths(config)

    if os.path.exists(paths["embeddings"]):
        embeddings = np.load(paths["embeddings"])
        ticket_ids = np.load(
            paths["ticket_ids"],
            allow_pickle=True
        ).tolist()
    else:
        embeddings = np.array([]).reshape(0, len(new_embedding))
        ticket_ids = []

    new_emb_array = np.array([new_embedding])

    if embeddings.shape[0] == 0:
        embeddings = new_emb_array
    else:
        embeddings = np.vstack([embeddings, new_emb_array])

    ticket_ids.append(new_ticket_id)

    np.save(paths["embeddings"], embeddings)
    np.save(paths["ticket_ids"], np.array(ticket_ids))

    print(f"Embedding appended for {new_ticket_id}")
    print(f"Total in index: {len(ticket_ids)}")


if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE_DIR)

    from ticketrepoagent.ingest import (
        load_config, load_tickets, clean_tickets
    )

    config  = load_config()
    tickets = load_tickets(config)
    tickets = clean_tickets(tickets, config)

    # ── Test 1: Create master repo and add tickets ─
    print("\n── Test 1: Add 3 approved tickets ───────")
    test_tickets = tickets.iloc[:3]

    for _, ticket in test_tickets.iterrows():
        decision = {
            "ticket_id"  : ticket["ticket_id"],
            "best_score" : 0.75,
            "best_match_id": "None"
        }
        append_approved_issue(
            ticket.to_dict(),
            decision,
            approver_id   = "SUB001",
            approver_name = "Subrasethu",
            config        = config,
            sop_reference = "SOP-TC-2025-042"
        )

    # ── Test 2: Add ticket without SOP reference ──
    print("\n── Test 2: Add ticket without SOP ───────")
    ticket4   = tickets.iloc[3]
    decision4 = {
        "ticket_id"  : ticket4["ticket_id"],
        "best_score" : 0.71,
        "best_match_id": "None"
    }
    append_approved_issue(
        ticket4.to_dict(),
        decision4,
        approver_id   = "SUB001",
        approver_name = "Subrasethu",
        config        = config,
        sop_reference = None
    )

   # ── Test 3: Mark SNW-002 as Obsolete ─────────
    print("\n── Test 3: Mark SNW-002 as Obsolete ─────")
    mark_obsolete(
        ticket_id       = "SNW-002",
        updated_by_id   = "SUB001",
        updated_by_name = "Subrasethu",
        reason          = "Excel plugin v3.2 replaced by v4.0",
        config          = config,
        new_validity    = "Obsolete"
    )

    # ── Test 4: Add SOP to SNW-004 later ─────────
    print("\n── Test 4: Tag SOP to SNW-004 ───────────")
    update_sop_reference(
        ticket_id      = "SNW-004",
        sop_reference  = "SOP-TC-2025-089",
        updated_by_name= "Subrasethu",
        config         = config
    )

    # ── Test 5: Show only Active issues ───────────
    print("\n── Test 5: Active issues only ───────────")
    active = get_active_issues(config)

    # ── Test 6: Mark SNW-003 as Under Review ──────
    print("\n── Test 6: Mark SNW-003 as Under Review ─")
    mark_obsolete(
        ticket_id       = "SNW-003",
        updated_by_id   = "SUB001",
        updated_by_name = "Subrasethu",
        reason          = "Resolution being reviewed after TC upgrade",
        config          = config,
        new_validity    = "Under Review"
    )

    # ── Test 7: Try invalid validity value ────────
    print("\n── Test 7: Test invalid validity ────────")
    mark_obsolete(
        ticket_id       = "SNW-004",
        updated_by_id   = "SUB001",
        updated_by_name = "Subrasethu",
        reason          = "Testing invalid value",
        config          = config,
        new_validity    = "Expired"
    )
