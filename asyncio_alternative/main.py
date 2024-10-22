import json
import asyncio
import aiohttp
import sys
import os
import json

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "app")))
from constants import ENDPOINT, LIST_CORP_PAYLOAD, CORP_BY_ID_PAYLOAD

PAGE_RANGE = list(range(1, 28))


async def post_request(session, payload, endpoint=ENDPOINT):
    async with session.post(endpoint, json=payload) as response:
        response.raise_for_status()
        return await response.json()


async def get_corp_list(session, page, payload=LIST_CORP_PAYLOAD):
    payload["variables"]["page"] = page
    data = await post_request(session, payload)
    corp_ids = data["data"]["corporates"]["rows"]
    return corp_ids


async def get_corp(session, corp_id, payload=CORP_BY_ID_PAYLOAD):
    payload["variables"]["id"] = corp_id
    data = await post_request(session, payload)
    return data["data"]["corporate"]


async def fetch_all_pages(pages=PAGE_RANGE):
    async with aiohttp.ClientSession() as session:
        tasks = [get_corp_list(session, page) for page in pages]
        results = await asyncio.gather(*tasks)
        flat = [corp["id"] for sublist in results for corp in sublist]
        return flat


async def fetch_corps(ids):
    async with aiohttp.ClientSession() as session:
        tasks = [get_corp(session, corp_id) for corp_id in ids]
        results = await asyncio.gather(*tasks)
        return results


async def main():
    corp_ids = await fetch_all_pages()
    res = await fetch_corps(corp_ids)
    with open("corp_data.json", "w") as f:
        f.write(json.dumps(res, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
