# ─────────────────────────────────────────────────
# approval_ui.py
# Panel dashboard for human review and approval
# of new issues detected by the agent
# ─────────────────────────────────────────────────

import os
import sys
import panel as pn
import pandas as pd
from datetime import datetime

# Auto detect project root
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from ticketrepoagent.ingest  import load_config
from ticketrepoagent.repo    import (
    append_approved_issue,
    mark_obsolete,
    update_sop_reference,
    get_master_repo_summary,
    load_master_repo
)

# ── Initialise Panel with a clean theme ──────────
pn.extension(sizing_mode="stretch_width")

# ── Load config once at startup ──────────────────
config          = load_config()
validity_options = config.get("approval", {}).get(
    "validity_options",
    ["Active", "Obsolete", "Under Review"]
)
sop_prefix      = config.get("master_repo", {}).get(
    "sop_prefix", "SOP-AMS-"
)


def build_review_card(issue, on_approve, on_reject, on_hold):
    """
    Builds one review card for a single new issue.
    Shows all details and action buttons.

    issue      = decision dictionary from similarity.py
    on_approve = function called when Approve clicked
    on_reject  = function called when Reject clicked
    on_hold    = function called when Under Review clicked
    """
    ticket_id   = issue["ticket_id"]
    description = issue["description"]
    best_score  = issue["best_score"]
    top_matches = issue["top_matches"]

    # ── Ticket details section ───────────────────
    title = pn.pane.Markdown(
        f"### Ticket: {ticket_id}",
        styles={"color": "#0D47A1", "font-weight": "bold"}
    )

    desc_box = pn.pane.Markdown(
        f"**Issue Description:**\n\n{description}",
        styles={
            "background" : "#E3F2FD",
            "padding"    : "10px",
            "border-radius": "8px"
        }
    )

    score_text = pn.pane.Markdown(
        f"**Similarity Score:** `{best_score}` "
        f"(threshold: `{config['similarity']['threshold']}`)"
    )

    # ── Top similar issues section ───────────────
    matches_text = "**Top Similar Issues in Master Repo:**\n\n"
    for match in top_matches:
        matches_text += (
            f"- `{match['ticket_id']}` — "
            f"similarity: `{match['score']}`\n"
        )

    matches_box = pn.pane.Markdown(
        matches_text,
        styles={
            "background"   : "#F3E5F5",
            "padding"      : "10px",
            "border-radius": "8px"
        }
    )

    # ── Approver details inputs ──────────────────
    approver_id_input = pn.widgets.TextInput(
        name        = "Approver ID",
        placeholder = "Enter your employee ID e.g. SUB001",
        width       = 300
    )

    approver_name_input = pn.widgets.TextInput(
        name        = "Approver Name",
        placeholder = "Enter your full name",
        width       = 300
    )

    # ── SOP reference input ──────────────────────
    sop_input = pn.widgets.TextInput(
        name        = "SOP Reference (optional)",
        placeholder = f"e.g. {sop_prefix}2025-042",
        width       = 300
    )

    # ── Rejection reason input ───────────────────
    reject_reason_input = pn.widgets.TextAreaInput(
        name        = "Rejection / Hold Reason",
        placeholder = "Enter reason for rejection or hold...",
        height      = 80,
        width       = 400
    )

    # ── Status message ───────────────────────────
    status_msg = pn.pane.Markdown("")

    # ── Action buttons ───────────────────────────
    approve_btn = pn.widgets.Button(
        name        = "Approve",
        button_type = "success",
        width       = 120
    )

    reject_btn = pn.widgets.Button(
        name        = "Reject",
        button_type = "danger",
        width       = 120
    )

    hold_btn = pn.widgets.Button(
        name        = "Under Review",
        button_type = "warning",
        width       = 140
    )

    # ── Button click handlers ────────────────────
    def on_approve_click(event):
        """Called when Approve button is clicked"""

        # Validate approver ID
        if not approver_id_input.value.strip():
            status_msg.object = (
                "⚠️ Please enter your Approver ID!"
            )
            return

        # Validate approver name
        if not approver_name_input.value.strip():
            status_msg.object = (
                "⚠️ Please enter your Approver Name!"
            )
            return

        # Disable buttons immediately to prevent
        # double clicking while processing
        approve_btn.disabled = True
        reject_btn.disabled  = True
        hold_btn.disabled    = True

        # Show processing message
        status_msg.object = "⏳ Processing approval..."

        try:
            on_approve(
                issue,
                approver_id   = approver_id_input.value.strip(),
                approver_name = approver_name_input.value.strip(),
                sop_reference = sop_input.value.strip()
            )
            # Show success message
            status_msg.object = (
                f"✅ **{ticket_id} Approved successfully!** "
                f"Saved to master repo by "
                f"{approver_name_input.value.strip()}"
            )
            print(f"UI: Approval complete for {ticket_id}")

        except Exception as e:
            # If error occurs re-enable buttons
            status_msg.object = (
                f"❌ Error during approval: {str(e)}\n\n"
                f"Please try again!"
            )
            approve_btn.disabled = False
            reject_btn.disabled  = False
            hold_btn.disabled    = False
            print(f"UI ERROR: {e}")

    def on_reject_click(event):
        """Called when Reject button is clicked"""
        if not approver_id_input.value.strip():
            status_msg.object = (
                "⚠️ Please enter your Approver ID!"
            )
            return
        if not reject_reason_input.value.strip():
            status_msg.object = (
                "⚠️ Please enter a rejection reason!"
            )
            return

        on_reject(
            issue,
            approver_id   = approver_id_input.value.strip(),
            approver_name = approver_name_input.value.strip(),
            reason        = reject_reason_input.value.strip()
        )
        status_msg.object = (
            f"❌ **{ticket_id} Rejected** — "
            f"{reject_reason_input.value.strip()}"
        )
        approve_btn.disabled = True
        reject_btn.disabled  = True
        hold_btn.disabled    = True

    def on_hold_click(event):
        """Called when Under Review button is clicked"""
        if not approver_id_input.value.strip():
            status_msg.object = (
                "⚠️ Please enter your Approver ID!"
            )
            return

        on_hold(
            issue,
            approver_id   = approver_id_input.value.strip(),
            approver_name = approver_name_input.value.strip(),
            reason        = reject_reason_input.value.strip()
        )
        status_msg.object = (
            f"🔄 **{ticket_id} marked Under Review** by "
            f"{approver_name_input.value.strip()}"
        )
        approve_btn.disabled = True
        reject_btn.disabled  = True
        hold_btn.disabled    = True

    # ── Wire buttons to handlers ─────────────────
    approve_btn.on_click(on_approve_click)
    reject_btn.on_click(on_reject_click)
    hold_btn.on_click(on_hold_click)

    # ── Assemble the card layout ─────────────────
    buttons_row = pn.Row(
        approve_btn,
        reject_btn,
        hold_btn
    )

    card = pn.Card(
        title,
        desc_box,
        score_text,
        matches_box,
        pn.layout.Divider(),
        pn.pane.Markdown("**Your Details:**"),
        approver_id_input,
        approver_name_input,
        sop_input,
        reject_reason_input,
        buttons_row,
        status_msg,
        title       = f"Review: {ticket_id}",
        collapsed   = False,
        styles      = {
            "background"   : "#FFFFFF",
            "border"       : "1px solid #E0E0E0",
            "border-radius": "12px",
            "margin-bottom": "16px"
        }
    )

    return card


def build_master_repo_tab(config):
    """
    Builds the Master Repo tab showing all
    validated issues with their validity status.
    """
    master_df = load_master_repo(config)

    if master_df.empty:
        return pn.pane.Markdown(
            "### No issues in master repo yet!"
        )

    # Show summary counts
    active_count  = len(
        master_df[master_df["validity"] == "Active"]
    )
    obsolete_count = len(
        master_df[master_df["validity"] == "Obsolete"]
    )
    review_count  = len(
        master_df[master_df["validity"] == "Under Review"]
    )

    summary = pn.pane.Markdown(
        f"**Total:** {len(master_df)}  |  "
        f"**Active:** {active_count}  |  "
        f"**Obsolete:** {obsolete_count}  |  "
        f"**Under Review:** {review_count}"
    )

    # Show table
    table = pn.widgets.DataFrame(
        master_df[[
            "issue_id", "issue_text", "approver_name",
            "sop_reference", "validity", "approved_at"
        ]],
        name     = "Master Repository",
        width    = 900,
        disabled = True
    )

    return pn.Column(summary, table)


def run_approval_ui(new_issues, new_tickets_df,
                    new_embeddings, config):
    """
    Main function to launch the approval dashboard.

    new_issues      = list of decision dicts from similarity.py
    new_tickets_df  = DataFrame of new tickets
    new_embeddings  = embeddings for new tickets
    config          = project config
    """
    # ── Track decisions ──────────────────────────
    approved_list = []
    rejected_list = []

    # ── Callback functions ───────────────────────
    def handle_approve(issue, approver_id,
                       approver_name, sop_reference):
        ticket_id = issue["ticket_id"]

        # Debug — print what we are looking for
        print(f"\nApproving ticket: {ticket_id}")
        print(f"Approver ID     : {approver_id}")
        print(f"Approver Name   : {approver_name}")
        print(f"SOP Reference   : {sop_reference}")

        # Find ticket row safely
        matching_rows = new_tickets_df[
            new_tickets_df["ticket_id"].astype(str).str.strip()
            == str(ticket_id).strip()
        ]

        if matching_rows.empty:
            print(f"WARNING: ticket {ticket_id} not found "
                  f"in new_tickets_df!")
            print(f"Available IDs: "
                  f"{new_tickets_df['ticket_id'].tolist()}")
            # Build ticket dict from issue dict directly
            ticket_row = {
                "ticket_id"  : ticket_id,
                "description": issue.get("description", ""),
                "resolution" : "",
                "category"   : "",
                "priority"   : "",
                "source"     : "CSV"
            }
        else:
            ticket_row = matching_rows.iloc[0].to_dict()
            print(f"Ticket found: {ticket_row.get('description','')[:50]}")

        try:
            append_approved_issue(
                ticket        = ticket_row,
                decision      = issue,
                approver_id   = approver_id,
                approver_name = approver_name,
                config        = config,
                sop_reference = sop_reference
            )
            approved_list.append(ticket_id)
            print(f"SUCCESS: {ticket_id} approved and "
                  f"saved to master repo!")
        except Exception as e:
            print(f"ERROR approving {ticket_id}: {e}")

    def handle_reject(issue, approver_id,
                      approver_name, reason):
        ticket_id = issue["ticket_id"]
        rejected_list.append({
            "ticket_id"    : ticket_id,
            "rejected_by"  : approver_name,
            "approver_id"  : approver_id,
            "reason"       : reason,
            "rejected_at"  : datetime.now().strftime(
                                 "%Y-%m-%d %H:%M:%S")
        })
        print(f"REJECTED: {ticket_id} — {reason}")

    def handle_hold(issue, approver_id,
                    approver_name, reason):
        ticket_id  = issue["ticket_id"]
        ticket_row = new_tickets_df[
            new_tickets_df["ticket_id"] == ticket_id
        ].iloc[0].to_dict()

        mark_obsolete(
            ticket_id       = ticket_id,
            updated_by_id   = approver_id,
            updated_by_name = approver_name,
            reason          = reason if reason else
                              "Marked Under Review",
            config          = config,
            new_validity    = "Under Review"
        )
        print(f"UNDER REVIEW: {ticket_id}")

    # ── Build header ─────────────────────────────
    header = pn.pane.Markdown(
        "# AMS Knowledge Agent — Approval Dashboard\n"
        f"**{len(new_issues)} new issue(s) "
        f"detected for review**",
        styles={"color": "#0D47A1"}
    )

    agent_info = pn.pane.Markdown(
        f"**Run date:** {datetime.now().strftime('%Y-%m-%d %H:%M')}  |  "
        f"**Similarity threshold:** "
        f"`{config['similarity']['threshold']}`  |  "
        f"**Source:** CSV"
    )

    divider = pn.layout.Divider()

    # ── Build review cards ───────────────────────
    if not new_issues:
        review_content = pn.pane.Markdown(
            "### No new issues detected this week!\n\n"
            "All tickets matched existing master repo entries."
        )
    else:
        cards = [
            build_review_card(
                issue,
                on_approve = handle_approve,
                on_reject  = handle_reject,
                on_hold    = handle_hold
            )
            for issue in new_issues
        ]
        review_content = pn.Column(*cards)

    # ── Build tabs ───────────────────────────────
    review_tab     = pn.Column(
        header,
        agent_info,
        divider,
        review_content
    )
    master_repo_tab = build_master_repo_tab(config)

    tabs = pn.Tabs(
        ("New Issues for Review", review_tab),
        ("Master Repository",    master_repo_tab)
    )

    # ── Launch dashboard ─────────────────────────
    tabs.servable()
    pn.serve(
        tabs,
        port      = 5006,
        show      = True,
        title     = "AMS Knowledge Agent"
    )

    return approved_list, rejected_list


if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE_DIR)

    from ticketrepoagent.ingest      import (
        load_tickets, clean_tickets
    )
    from ticketrepoagent.embedder    import (
        load_model, generate_embeddings, load_embeddings
    )
    from ticketrepoagent.similarity  import process_new_tickets

    # ── Load everything ──────────────────────────
    config  = load_config()
    tickets = load_tickets(config)
    tickets = clean_tickets(tickets, config)

    # ── Load saved embeddings ────────────────────
    master_embeddings, master_ids = load_embeddings(config)

    if master_embeddings is None:
        print("No embeddings found!")
        print("Run embedder.py first!")
    else:
        # ── Simulate new incoming tickets ────────
        # Use last 3 tickets as new incoming
        new_tickets = tickets.iloc[7:]
        new_emb     = master_embeddings[7:]
        master_emb  = master_embeddings[:7]
        master_id   = master_ids[:7]

        # ── Run similarity check ─────────────────
        known, new_issues = process_new_tickets(
            new_tickets,
            new_emb,
            master_emb,
            master_id,
            config
        )

        print(f"\nKnown issues : {len(known)}")
        print(f"New issues   : {len(new_issues)}")
        print(f"\nLaunching approval dashboard...")
        print(f"Opening browser at http://localhost:5006")

        # ── Launch Panel UI ──────────────────────
        approved, rejected = run_approval_ui(
            new_issues    = new_issues,
            new_tickets_df= new_tickets,
            new_embeddings= new_emb,
            config        = config
        )
