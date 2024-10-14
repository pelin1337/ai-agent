from celery import Celery, group, chord
import requests
import json
import glob, os
from constants import ENDPOINT, LIST_CORP_PAYLOAD, CORP_BY_ID_PAYLOAD

app = Celery("tasks", broker="redis://redis:6379/0", backend="redis://redis:6379/1")
session = requests.Session()


def post_request(payload, endpoint=ENDPOINT):
    """
    General post_request form.

    Returns response.json if status=200
    Raises the status otherwise.
    """
    response = session.post(endpoint, json=payload)
    response.raise_for_status()
    return response.json()


@app.task
def get_corp_list(page, payload=LIST_CORP_PAYLOAD):
    """
    Fetches data for a specific page.
    Creates a group of tasks to receive and write data.
    """

    payload["variables"]["page"] = page
    data = post_request(payload)
    corp_ids = data["data"]["corporates"]["rows"]

    return chord((get_corp_data.s(id["id"]) for id in corp_ids))(
        on_batch_complete.s(page)
    )


@app.task
def get_corp_data(corp_id, payload=CORP_BY_ID_PAYLOAD):
    """
    Returns the corp data using corp's id.
    """
    payload["variables"]["id"] = corp_id
    data = post_request(payload)
    return data["data"]["corporate"]


@app.task
def on_batch_complete(results, page):
    """
    Callback to get_corp_list's chord.
    Writes the result on a file.
    """
    filename = f"./data/corp_{page}.json"

    with open(filename, "w") as f:
        json.dump(results, f, indent=2)
