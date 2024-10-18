import json

from dotenv import load_dotenv
import os
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
from sklearn.cluster import KMeans
import numpy as np
from scipy.spatial.distance import cosine
from sklearn.metrics import (
    silhouette_score,
    calinski_harabasz_score,
    davies_bouldin_score,
)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
with open("corp_data.json", "r") as f:
    CORP_DATA = json.load(f)

LLM = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY)

EMBEDDING = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=GOOGLE_API_KEY,
    task_type="semantic_similarity",
)


def parse_query(query, llm):
    content = f"""
    Please extract filtering and grouping criteria from the following query. 
    Use the valid filter criteria and map any unspecified terms to the closest valid option. 

    **Valid Filter Criteria:** 
    - name
    - description
    - city
    - country
    - themes

    **Valid Themes:** 
    - Analytics, Digital Transformation, Industry 4.0, Automotive, Health Care, Artificial Intelligence, 
    Smart Home, Machine Learning, Consulting, Smart Supply Chain, Sharing Economy, Robotics, Training, 
    Safety, Market Research, Cyber Security, InsurTech, Retail Technology, Cloud Computing, Information Services, 
    Computer Vision, Marketing, CRM, LegalTech, Augmented Reality, Big Data, Advertising, Virtual Reality, 
    Digitalization, Supply Chain Management, Natural Language Processing, Smart Grid, Future of Work, 
    Smart City, Apps, 3D Technology, CleanTech, Security, Manufacturing, Business Intelligence, Collaboration, 
    B2B, Logistics, Enterprise Software, Digital Marketing, Data Integration, Luxury, Automation, MarTech, 
    Autonomous Vehicles, FinTech, New Mobility, Insurance, PropTech, Consumer Electronics, Internet of Things, 
    Recruiting, Human Resources, Video, RegTech, MarkTech, InsurTech, E-Commerce, Social Media, SaaS, 
    Sustainability, Circular Economy, Predictive Analytics, Social Good (Economy), Education, Electronics, 
    Industrial Automation, Cybersecurity, HealthTech.

    - If the query mentions a theme not in the list, map it to the closest match.

    **Valid Grouping Criteria:** 
    - themes
    - geography

    - If the query mentions a grouping criterion not in the list, map it to 'default'.
    - If the query does not mention a grouping criterion. map it to 'default'.

    Respond only in JSON format with fields `filter` and `group_by`. 
    While using city and country, use hq_city and hq_country as their column names.
    Example format:
    {{
    "filter": {{"name": "example", "country": "example_country"}},
    "group_by": "example_criteria"
    }}

    Do not include JSON header.
    Query: '{query}'
    """

    prompt = [{"role": "user", "content": content}]
    response = llm.invoke(prompt)
    response = response.content
    parsed_content = json.loads(response)

    parsed_query = {
        "filter": parsed_content.get("filter", {}),
        "group_by": parsed_content.get("group_by", None),
    }

    parsed_result = {k: v for k, v in parsed_query.items() if v is not None}

    return parsed_result


def fetch_data(filter_criteria, corp_data):
    filtered_corps = []
    for corp in corp_data:
        add_other = True
        add_theme = False
        for key, value in filter_criteria.items():
            if key == "themes":
                for theme in value:
                    if theme in corp["themes"]:
                        add_theme = True
                        break
            else:
                corp_value = str(corp.get(key, "")).lower()
                if corp_value.find(value.lower()) == -1:
                    add_other = False
        if "themes" in filter_criteria.keys():
            if add_other and add_theme:
                filtered_corps.append(corp)
        else:
            if add_other:
                filtered_corps.append(corp)
    return filtered_corps


def get_embedding(text, embedding):
    query_embeddings = embedding.embed_query(text)
    return query_embeddings


def cluster(corps, group_by, n_clusters=5):
    if group_by == "themes":
        text_data = [
            " ".join(
                [
                    (theme[0] + " ") * int(theme[1])
                    for theme in corporate["startup_themes"]
                    if theme[0] != "Other"
                ]
            )
            for corporate in corps
        ]
    elif group_by == "geography":
        text_data = [
            " ".join([corporate.get("hq_city"), corporate.get("hq_country")])
            for corporate in corps
        ]

    else:
        text_data = [
            " ".join(
                [
                    corporate["name"],
                    corporate["description"],
                    " ".join(
                        [
                            (theme[0] + " ") * int(theme[1])
                            for theme in corporate["startup_themes"]
                            if theme[0] != "Other"
                        ]
                    ),
                ]
            )
            for corporate in corps
        ]

    embeddings = [get_embedding(text, EMBEDDING)[50:] for text in text_data]
    X = np.array(embeddings)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = kmeans.fit_predict(X)

    return clusters, X


def quality_assurance(clusters, embeddings):

    # The silhouette score measures how similar a data point is to its own cluster (cohesion) compared to other clusters (separation).
    # It ranges from -1 to 1, where:
    # +1 indicates that the sample is far away from neighboring clusters and appropriately clustered.
    # 0 indicates that the sample is on or very close to the decision boundary between two neighboring clusters.
    # -1 indicates that the sample might be placed in the wrong cluster.
    silhouette_avg = silhouette_score(embeddings, clusters)

    # The Calinski-Harabasz score (also known as the Variance Ratio Criterion) measures the ratio of
    # the sum of between-cluster dispersion (variance) to within-cluster dispersion.
    # A higher score indicates better-defined clusters.
    calinski_harabasz = calinski_harabasz_score(embeddings, clusters)

    # The Davies-Bouldin score is a measure of cluster quality that evaluates the ratio of
    # within-cluster distances to between-cluster distances.
    # A lower score indicates better clustering.
    davies_bouldin = davies_bouldin_score(embeddings, clusters)

    silhouette_threshold = 0.5
    calinski_threshold = 500
    davies_bouldin_threshold = 1.5

    qa_pass = True
    qa_reason = []

    if silhouette_avg < silhouette_threshold:
        qa_pass = False
        qa_reason.append(f"Low silhouette score: {silhouette_avg}")

    if calinski_harabasz < calinski_threshold:
        qa_pass = False
        qa_reason.append(f"Low Calinski-Harabasz score: {calinski_harabasz}")

    if davies_bouldin > davies_bouldin_threshold:
        qa_pass = False
        qa_reason.append(f"High Davies-Bouldin score: {davies_bouldin}")

    return qa_pass, qa_reason


criteria = parse_query("Get the companies in France", LLM)
print(criteria)
filter_criteria = criteria["filter"]
group_criteria = criteria["group_by"]
corps = fetch_data(filter_criteria, CORP_DATA["corps"])

with open("filtered_corps.json", "w") as f:
    f.write(json.dumps(corps, indent=2))


clusters, embeddings = cluster(corps, group_criteria)

qa_pass, qa_reason = quality_assurance(clusters, embeddings)

print(qa_pass, qa_reason)
