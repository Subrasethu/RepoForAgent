import os
import numpy as np
from numpy.linalg import norm

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def cosine_similarity(vec1, vec2):
    """
    Calculates how similar two vectors are.
    Returns a score between 0 and 1.
    0 = completely different
    1 = identical meaning
    """
    return np.dot(vec1, vec2) / (norm(vec1) * norm(vec2))


def find_similar_tickets(new_embedding, master_embeddings, ticket_ids, config):
    """
    Compares a new ticket embedding against ALL
    existing embeddings in the master repo.

    Returns top N most similar tickets and their scores.
    """
    top_n     = config["similarity"]["top_matches"]
    scores    = []

    # Compare new ticket against every master repo ticket
    for i, master_emb in enumerate(master_embeddings):
        score = cosine_similarity(new_embedding, master_emb)
        scores.append({
            "ticket_id" : ticket_ids[i],
            "score"     : round(float(score), 4)
        })

    # Sort by score highest first
    scores = sorted(scores, key=lambda x: x["score"], reverse=True)

    # Return only top N matches
    return scores[:top_n]


def make_decision(new_ticket, new_embedding, master_embeddings, ticket_ids, config):
    """
    Main decision function.
    Takes a new ticket and decides if it is:
    - KNOWN   : similar to existing issue → skip
    - NEW     : genuinely new issue → send for approval

    Returns a decision dictionary with full details.
    """
    threshold  = config["similarity"]["threshold"]
    desc_col   = config["csv"]["description_column"]

    # Find top similar tickets
    top_matches = find_similar_tickets(
        new_embedding,
        master_embeddings,
        ticket_ids,
        config
    )

    # Best match is the first one (highest score)
    best_score     = top_matches[0]["score"] if top_matches else 0.0
    best_match_id  = top_matches[0]["ticket_id"] if top_matches else "None"

    # Make decision based on threshold
    if best_score >= threshold:
        decision = "KNOWN"
        action   = "Skip - already in master repo"
    else:
        decision = "NEW"
        action   = "Send for human approval"

    return {
        "ticket_id"     : new_ticket.get("ticket_id", "Unknown"),
        "description"   : new_ticket.get(desc_col, ""),
        "decision"      : decision,
        "action"        : action,
        "best_score"    : best_score,
        "best_match_id" : best_match_id,
        "top_matches"   : top_matches
    }


def process_new_tickets(new_tickets, new_embeddings, master_embeddings,
                        master_ids, config):
    """
    Processes ALL new tickets and returns two lists:
    - known_issues  : tickets already in master repo
    - new_issues    : genuinely new tickets for approval
    """
    known_issues = []
    new_issues   = []

    print(f"\nProcessing {len(new_tickets)} tickets...")
    print(f"Similarity threshold : {config['similarity']['threshold']}")
    print("-" * 50)

    for i, (_, ticket) in enumerate(new_tickets.iterrows()):
        new_emb  = new_embeddings[i]
        decision = make_decision(
            ticket.to_dict(),
            new_emb,
            master_embeddings,
            master_ids,
            config
        )

        if decision["decision"] == "KNOWN":
            known_issues.append(decision)
            status = "KNOWN  ✓"
        else:
            new_issues.append(decision)
            status = "NEW    !"

        print(f"  {decision['ticket_id']} → {status} "
              f"(score: {decision['best_score']:.4f} "
              f"vs {decision['best_match_id']})")

    print("-" * 50)
    print(f"Known issues : {len(known_issues)}")
    print(f"New issues   : {len(new_issues)}")

    return known_issues, new_issues


if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE_DIR)

    from ticketrepoagent.ingest   import load_config, load_tickets, clean_tickets
    from ticketrepoagent.embedder import load_model, generate_embeddings, load_embeddings

    # Step 1: Load config
    config = load_config()

    # Step 2: Load tickets
    tickets = load_tickets(config)
    tickets = clean_tickets(tickets, config)

    # Step 3: Load saved embeddings from disk
    # These were saved by embedder.py in Step 3
    master_embeddings, master_ids = load_embeddings(config)

    if master_embeddings is None:
        print("No embeddings found - run embedder.py first!")
    else:
        # Step 4: Simulate new incoming tickets
        # We use last 3 tickets as "new" incoming tickets
        # and first 7 as "master repo"
        print("\nSimulating weekly ticket check...")
        print("Master repo     : first 7 tickets (SNW-001 to SNW-007)")
        print("Incoming tickets: last 3 tickets  (SNW-008, SNW-009, SNW-010)")
        print("+ SNW-006 which is similar to SNW-001\n")

        master_emb  = master_embeddings[:7]
        master_id   = master_ids[:7]
        new_tickets = tickets.iloc[5:]
        new_emb     = master_embeddings[5:]

        # Step 5: Process and decide
        known, new = process_new_tickets(
            new_tickets,
            new_emb,
            master_emb,
            master_id,
            config
        )

        # Step 6: Show new issues that need approval
        if new:
            print(f"\n── New Issues for Human Approval ────────")
            for issue in new:
                print(f"\n  Ticket    : {issue['ticket_id']}")
                print(f"  Issue     : {issue['description'][:60]}...")
                print(f"  Score     : {issue['best_score']}")
                print(f"  Action    : {issue['action']}")
                print(f"  Top matches:")
                for match in issue["top_matches"]:
                    print(f"    - {match['ticket_id']} "
                          f"(similarity: {match['score']})")
