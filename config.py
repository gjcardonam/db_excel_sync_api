
import json

def load_db_config(json_path, empresa):
    with open(json_path, "r") as f:
        config = json.load(f)
    return config[empresa]
