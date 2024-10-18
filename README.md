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

```
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

```
{"status":
  "Batch process initiated",
  "batch_id":"15f178d7-b7a2-4dab-91f1-33ccb735f9f0"}
```

The batch_id can be used to track the process via `/status/{batch_id}` endpoint. For each page, the process will create corp_{page}.json files, which hold the corporate data. This data is retrieved under agent/data for further use. 



## Phase 5 - AI Agent

### Preprocessing

After gathering all the files together, let's precompute each embedding. This will be faster, and cost efficient. There can be different ways depending on need and user experience, but I chose the following to _define_ a company:

```
- name
- description
- city 
- country 
- themes
```

