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

The `batch_id` can be used to track the process via `/status/{batch_id}` endpoint. For each page, the process will create corp\*{page}.json files, which hold the corporate data. This data is retrieved under agent/data for further use.

### Asyncio Alternative Solution

The solution can be found under the folder `asyncio_alternative`. Can simply run with `python main.py`. Working with asyncio is simple, you can define the async workflows yourself + saves from Celery overhead. It took 4-5 seconds including file write.

## Phase 5 - LangGraph AI Agent

### Preprocessing

Gathering of the files and modifications to data structure can be found in `preprocessing.py`.

### User Queries

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

### Data Fetcher Node

After extracting selection filters from user query, data fetcher node scans all the data and updates graph state. where graph state is:

```python
class State(TypedDict):
    query: str
    parsed_query: dict
    filtered_corps: List[Dict]
    clusters: np.ndarray
    embeddings: np.ndarray
    qa_result: Dict
```

### Clustering Node

While clustering the companies based on their text data only, a method that understands the semantic meaning of the words will be better. Our dataset is very small, so using a method like TF-IDF would not be the best approach.

For clustering to perform better, I also created the text data so that each startup theme's explanation repeats the number of times a corporate has a startup under that theme. Better explained in code:

```python
(theme[0] + " ") * int(theme[1])
for theme in corporate["startup_themes"]
if theme[0] != "Other"
```

We need to include word embedding for semantics. Instead of using a gensim model, I used google's text-embedding-004 model to get word embeddings, then performed clustering using KMeans method.

### Quality Assurance Node

To assure the quality of clusters, we can use well-known metrics to calculate how well they are structured. The metrics I've used (from `sci-kit learn`):

#### Silhouette Score

The silhouette score measures how similar a data point is to its own cluster (cohesion) compared to other clusters (separation).It ranges from -1 to 1, where:

- +1 indicates that the sample is far away from neighboring clusters and appropriately clustered.
- 0 indicates that the sample is on or very close to the decision boundary between two neighboring clusters.
- -1 indicates that the sample might be placed in the wrong cluster.

#### Calinski-Harabasz Score

The Calinski-Harabasz score (also known as the Variance Ratio Criterion) measures the ratio of the sum of between-cluster dispersion (variance) to within-cluster dispersion. A higher score indicates better-defined clusters.

#### Davies-Bouldin Score

The Davies-Bouldin score is a measure of cluster quality that evaluates the ratio of within-cluster distances to between-cluster distances. A lower score indicates better clustering.

### Example Query, Output and Improvements

The necessary code is in the file `agent.py`. `grouping_test.py` and `query_test.py` are some files I used while trying out function implementations (didn't delete them for myself.)

`python agent.py` will start the interactive client.

User query:

```
"Get the companies in AI and group them by their location"
```

Parsed query:

```json
{ "filter": { "themes": ["Artificial Intelligence"] }, "group_by": "geography" }
```

Dividing into clusters, each cluster counted based on country:

```json
[{'United States': 14, 'Portugal': 2, 'United Kingdom': 2, 'Italy': 1}

{'Germany': 21, 'Switzerland': 5, 'Austria': 2, 'Sweden': 1},

{'France': 12, 'Denmark': 1, 'South Korea': 2},

{'United Kingdom': 8, 'Italy': 1, 'Singapore': 1, 'United States': 20, 'China': 1, 'Japan': 1, 'Ireland': 1},

{'Netherlands': 5, 'Germany': 3, 'Japan': 1}]
```

Our approach so far groups same countries not-so-bad. 21 corporates from Germany being in the same group while only 3 companies being on other groups is promising. Also, Switzerland, Austria, and Sweden are in this group as well, which are closer countries to Germany.

Some possible improvement points:

- Trying out different clustering algorithms, observing their scores
- Deciding on cluster size dynamically
- Deciding which score ratings are 'OK' for the data we have, and on which scores QA should alert a warning
- Possible QA from LLM implementation
- Saving embeddings in a file
- Implement better error handling and logging overall
