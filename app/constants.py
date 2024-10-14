PAGE_RANGE = 28

ENDPOINT = "https://ranking.glassdollar.com/graphql"

CORP_BY_ID_QUERY = """
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
"""

LIST_CORP_QUERY = """
query ExampleQuery($filters: CorporateFilters, $page: Int, $sortBy: String) {
  corporates(filters: $filters, page: $page, sortBy: $sortBy) {
    rows {
      id
    }
  }
}
"""

LIST_CORP_PAYLOAD = {
    "variables": {"filters": {"hq_city": [], "industry": []}, "page": 27},
    "query": LIST_CORP_QUERY,
}

CORP_BY_ID_PAYLOAD = {
    "query": CORP_BY_ID_QUERY,
    "variables": {
        "id": "8483fc50-b82d-5ffa-5f92-6c72ac4bdaff",
    },
}
