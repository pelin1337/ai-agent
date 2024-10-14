from fastapi import FastAPI
from tasks import get_corp_list
from celery import group


app = FastAPI()

CORP_DATA_PATH = "corp_data.json"

PAGE_RANGE = list(range(1, 28))

batch_results = {}


@app.get("/crawl")
def crawl():
    batch_task = group(get_corp_list.s(page) for page in PAGE_RANGE)

    result = batch_task.apply_async()

    batch_results[result.id] = result

    return {"status": "Batch process initiated", "batch_id": result.id}


@app.get("/status/{batch_id}")
def status(batch_id):
    result = batch_results.get(batch_id)

    if not result:
        return {"status": "Invalid batch ID or batch does not exist"}

    if result.ready():
        return {"status": "Batch processing completed"}
    else:
        return {"status": "Batch processing in progress, please come back later"}
