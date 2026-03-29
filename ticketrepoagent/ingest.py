import os
import pandas as pd
import yaml

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def load_config(config_path=None):
    if config_path is None:
        config_path = os.path.join(BASE_DIR, "config.yaml")
    with open(config_path, "r") as f:
        config = yaml.safe_load(f)
    config["BASE_DIR"] = BASE_DIR
    return config

def load_tickets(config):
    input_folder = os.path.join(config["BASE_DIR"], config["paths"]["input_folder"])
    status_col   = config["csv"]["status_column"]
    resolved_val = config["csv"]["resolved_value"]
    all_tickets  = []
    print(f"Looking for CSV files in: {input_folder}")
    for filename in os.listdir(input_folder):
        if filename.endswith(".csv"):
            file_path = os.path.join(input_folder, filename)
            print(f"Reading file: {filename}")
            df = pd.read_csv(file_path)
            df = df[df[status_col] == resolved_val]
            all_tickets.append(df)
    if len(all_tickets) == 0:
        print("No CSV files found!")
        return pd.DataFrame()
    combined = pd.concat(all_tickets, ignore_index=True)
    print(f"Total resolved tickets loaded: {len(combined)}")
    return combined

def clean_tickets(df, config):
    desc_col = config["csv"]["description_column"]
    res_col  = config["csv"]["resolution_column"]
    df = df.dropna(subset=[desc_col, res_col])
    df[desc_col] = df[desc_col].str.strip()
    df[res_col]  = df[res_col].str.strip()
    df["combined_text"] = df[desc_col] + " " + df[res_col]
    print(f"Tickets after cleaning: {len(df)}")
    return df

if __name__ == "__main__":
    config  = load_config()
    tickets = load_tickets(config)
    tickets = clean_tickets(tickets, config)
    print("\nFirst 3 tickets:")
    print(tickets[["ticket_id", "description", "combined_text"]].head(3))