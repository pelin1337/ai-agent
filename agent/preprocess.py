import os
import json


def load_json_files(dir):
    data_dict = {"corps": []}

    for filename in os.listdir(dir):
        if filename.endswith(".json"):
            filepath = os.path.join(dir, filename)
            with open(filepath, "r", encoding="utf-8") as f:
                data = json.load(f)
                for corp in data:
                    themes = set()

                    # Unacceptable nulls

                    name = corp.get("name")
                    descrp = corp.get("description")
                    city = corp.get("hq_city")
                    country = corp.get("hq_country")

                    if (
                        name is None
                        or descrp is None
                        or city is None
                        or country is None
                    ):
                        continue

                    for st in corp["startup_themes"]:
                        if st[0] != "Other":
                            themes.add(st[0])

                    corp["themes"] = list(themes)
                    data_dict["corps"].append(corp)

    return data_dict


corp_data = load_json_files("./data")


with open("corp_data.json", "w") as f:
    f.write(json.dumps(corp_data, indent=2))
