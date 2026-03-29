import os
import numpy as np
import requests

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_model(config):
    ollama_url = config["embedding"]["ollama_url"]
    model_name = config["embedding"]["model_name"]
    print(f"Checking Ollama connection at: {ollama_url}")
    try:
        response = requests.get(f"{ollama_url}/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"Ollama is running!")
            print(f"Using model: {model_name}")
            return {"url": ollama_url, "model": model_name}
        else:
            print("Ollama returned unexpected response")
            return None
    except Exception as e:
        print(f"Cannot connect to Ollama: {e}")
        return None

def get_single_embedding(text, model_config):
    url        = model_config["url"]
    model_name = model_config["model"]
    response   = requests.post(
        f"{url}/api/embeddings",
        json={"model": model_name, "prompt": text},
        timeout=30
    )
    if response.status_code == 200:
        return response.json()["embedding"]
    else:
        print(f"Error: {response.text}")
        return None

def generate_embeddings(df, model_config):
    texts = df["combined_text"].tolist()
    total = len(texts)
    print(f"Generating embeddings for {total} tickets via Ollama...")
    embeddings = []
    for i, text in enumerate(texts):
        embedding = get_single_embedding(text, model_config)
        if embedding is not None:
            embeddings.append(embedding)
        else:
            embeddings.append([0.0] * 768)
        print(f"  Processed {i+1}/{total} tickets", end="\r")
    embeddings = np.array(embeddings)
    print(f"\nEmbeddings shape : {embeddings.shape}")
    print(f"Each ticket      = {embeddings.shape[1]} numbers")
    return embeddings

def save_embeddings(embeddings, ticket_ids, config):
    output_folder = os.path.join(
        config["BASE_DIR"],
        config["paths"]["output_folder"]
    )
    os.makedirs(output_folder, exist_ok=True)
    emb_path = os.path.join(output_folder, "embeddings.npy")
    ids_path = os.path.join(output_folder, "ticket_ids.npy")
    np.save(emb_path, embeddings)
    np.save(ids_path, np.array(ticket_ids))
    print(f"Embeddings saved to : {emb_path}")
    print(f"Ticket IDs saved to : {ids_path}")

def load_embeddings(config):
    output_folder = os.path.join(
        config["BASE_DIR"],
        config["paths"]["output_folder"]
    )
    emb_path = os.path.join(output_folder, "embeddings.npy")
    ids_path = os.path.join(output_folder, "ticket_ids.npy")
    if not os.path.exists(emb_path):
        print("No saved embeddings found - generate first!")
        return None, None
    embeddings = np.load(emb_path)
    ticket_ids = np.load(ids_path, allow_pickle=True)
    print(f"Loaded {len(ticket_ids)} existing embeddings from disk")
    return embeddings, ticket_ids

if __name__ == "__main__":
    import sys
    sys.path.insert(0, BASE_DIR)
    from ticketrepoagent.ingest import load_config, load_tickets, clean_tickets

    config       = load_config()
    tickets      = load_tickets(config)
    tickets      = clean_tickets(tickets, config)
    model_config = load_model(config)

    if model_config is None:
        print("Ollama not running - please start Ollama and try again!")
    else:
        embeddings = generate_embeddings(tickets, model_config)
        ticket_ids = tickets["ticket_id"].tolist()
        save_embeddings(embeddings, ticket_ids, config)

        print("\n── Results ──────────────────────────────")
        print(f"Total tickets processed : {len(tickets)}")
        print(f"Embedding shape         : {embeddings.shape}")
        print(f"\nFirst ticket    : {tickets['ticket_id'].iloc[0]}")
        print(f"First 5 numbers : {embeddings[0][:5].round(4)}")

        from numpy.linalg import norm
        e1         = embeddings[0]
        e6         = embeddings[5]
        similarity = np.dot(e1, e6) / (norm(e1) * norm(e6))

        print(f"\n── Similarity Test ──────────────────────")
        print(f"SNW-001 vs SNW-006 similarity : {similarity:.4f}")
        print(f"Threshold in config           : 0.88")
        if similarity >= 0.88:
            print(f"Result: KNOWN ISSUE detected!")
        else:
            print(f"Result: NEW ISSUE - needs review")