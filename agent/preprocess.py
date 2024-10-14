import os
import pandas as pd
import json


def load_json_files(dir):
    data_list = []

    for filename in os.listdir(dir):
        if filename.endswith(".json"):
            filepath = os.path.join(dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                data_list.append(data)
    return data_list


json_data = load_json_files("./data")
