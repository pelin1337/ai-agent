## Phase 1 - Data Crawling

Inspecting a company's page, we see that `https://ranking.glassdollar.com/graphql` is queried for company information. For example, for Siemens, payload sent was

```
variables: {id: "8483fc50-b82d-5ffa-5f92-6c72ac4bdaff"}
query ($id: String!) {
  corporate(id: $id) {
    id
    name
    description
    logo_url
    hq_city
    hq_country
    website_url
    linkedin_url
    twitter_url
    startup_partners_count
    startup_partners {
      master_startup_id
      company_name
      logo_url: logo
      city
      website
      country
      theme_gd
      __typename
    }
    startup_themes
    startup_friendly_badge
    __typename
  }
}
```

This query will be sent for every company's id separately. To gather company ids, we can inspect graphql with an introspection query. Which returns a query `corporates`:

```json
{
            "name": "corporates",
            "description": null,
            "args": [
              {
                "name": "filters",
                "description": null,
                "type": {
                  "name": "CorporateFilters",
                  "kind": "INPUT_OBJECT",
                  "ofType": null
                }
              },
              {
                "name": "page",
                "description": null,
                "type": {
                  "name": "Int",
                  "kind": "SCALAR",
                  "ofType": null
                }
              },
              {
                "name": "sortBy",
                "description": null,
                "type": {
                  "name": "String",
                  "kind": "SCALAR",
                  "ofType": null
                }
              }
            ],
            "type": {
              "name": "CorporatesType",
              "kind": "OBJECT",
              "ofType": null
            }
          },
          ...
```

which means corporate data is held in pages. We can keep querying different pages for corporate ids. Then, we can use corporate query to get the relevant information.

## Phase 2-4 and Alternative Solution with Asyncio

We will set up 2 different instances, which:

- Celery worker + FastAPI
- Redis (for Celery to use)

Simple `docker-compose build` will create the instances. `docker-compose up` will start the containers. For crawling process to start, `curl http://localhost:8000/crawl` can be used. This endpoint will return:

```json
{
  "status": "Batch process initiated",
  "batch_id": "15f178d7-b7a2-4dab-91f1-33ccb735f9f0"
}
```

The batch*id can be used to track the process via `/status/{batch_id}` endpoint. For each page, the process will create corp*{page}.json files, which hold the corporate data. This data is retrieved under agent/data for further use.

## Phase 5 - LangGraph AI Agent

### Preprocessing

Gathering of the files and modifications to data structure can be found in `preprocessing.py`

### User queries

I've used Gemini 1.5 Flash model to process user queries. Queries are processed in such a way that:

```
name
description
city
country
themes
```

can be used as filters to get corporate data. To implement this type of filtering, I've also gathered all the valid themes in data. The LLM maps to the closest theme if user means filtering in _some other way_ that is close enough.

The user also can decide how to group selected corporates. The options are

```
themes
geography
default
```

where default grouping includes all of the filtering list mentioned above.

### Data fetcher node

After extracting selection filters from user query, data fetcher node scans all the data and updates graph state. where graph state is:

```python
class State(TypedDict):
    query: str
    parsed_query: dict
    filtered_corps: List[Dict]
    clustered_corps: List[Dict]
    qa_result: str
```

### Clustering node

While clustering the companies based on their text data only, a method that understands the semantic meaning of the words will be better. Our dataset is very small, so using a method like TF-IDF would not be the best approach.

For clustering to perform better, I also created the text data so that each startup theme's explanation repeats the number of times a corporate has a startup under that theme. Better explained in code:

```python
(theme[0] + " ") * int(theme[1])
for theme in corporate["startup_themes"]
if theme[0] != "Other"
```

We need to include word embedding for semantics. Instead of using a gensim model, I used google's text-embedding-004 model to get word embeddings, then performed clustering using KMeans method.

### Quality Assurance Node
