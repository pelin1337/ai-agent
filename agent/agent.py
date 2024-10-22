import os
import json
from typing_extensions import TypedDict, List, Dict
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
import numpy as np
from sklearn.cluster import KMeans
from sklearn.metrics import (
    silhouette_score,
    calinski_harabasz_score,
    davies_bouldin_score,
)
from dotenv import load_dotenv
from langgraph.graph import StateGraph, START, END
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

LLM = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY)

EMBEDDING = GoogleGenerativeAIEmbeddings(
    model="models/text-embedding-004",
    google_api_key=GOOGLE_API_KEY,
    task_type="semantic_similarity",
)

try:
    with open("corp_data.json", "r") as f:
        CORP_DATA = json.load(f)
except FileNotFoundError:
    logger.error("corp_data.json not found.")
    raise


class State(TypedDict):
    query: str
    parsed_query: dict
    filtered_corps: List[Dict]
    clusters: np.ndarray
    embeddings: np.ndarray
    qa_result: Dict
    error: str | None


def parse_query(state: State, llm=LLM) -> State:
    query = state["query"]
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
    Always return themes as a list, even if there is one theme.
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

    parsed_query = {k: v for k, v in parsed_query.items() if v is not None}
    return {"parsed_query": parsed_query, **state}


def fetch_data(state: State, corp_data=CORP_DATA["corps"]) -> State:
    filter_criteria = state["parsed_query"]["filter"]
    print(filter_criteria)
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

    if not filtered_corps:
        logger.warning("No companies matcher the filter criteria")
        return {"error": "No matching companies found", **state}
    print(filtered_corps)
    return {"filtered_corps": filtered_corps, **state}


def cluster(state: State, embedding=EMBEDDING, n_clusters=2) -> State:
    corps = state["filtered_corps"]
    group_by = state["parsed_query"]["group_by"]

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

    text_data_processed = []

    for data in text_data:
        text_data_processed.append(data.lower().split())

    embeddings = [embedding.embed_query(text)[50:] for text in text_data]
    X = np.array(embeddings)

    kmeans = KMeans(n_clusters=n_clusters, random_state=42)
    clusters = kmeans.fit_predict(X)

    return {"clusters": clusters, "embeddings": X, **state}


def quality_assurance(state: State) -> State:
    embeddings = state["embeddings"]
    clusters = state["clusters"]
    silhouette_avg = silhouette_score(embeddings, clusters)
    calinski_harabasz = calinski_harabasz_score(embeddings, clusters)
    davies_bouldin = davies_bouldin_score(embeddings, clusters)

    results = {}
    results["silhouette"] = silhouette_avg
    results["calinski-harabasz"] = calinski_harabasz
    results["davies-bouldin"] = davies_bouldin

    return {"qa_result": results, **state}


def create_graph() -> StateGraph:
    graph = StateGraph(State)

    graph.add_node("parse_query", parse_query)
    graph.add_node("fetch_data", fetch_data)
    graph.add_node("cluster", cluster)
    graph.add_node("quality_assurance", quality_assurance)

    graph.add_edge(START, "parse_query")
    graph.add_edge("parse_query", "fetch_data")
    graph.add_edge("fetch_data", "cluster")
    graph.add_edge("cluster", "quality_assurance")
    graph.add_edge("quality_assurance", END)

    return graph.compile()


def run_workflow(query: str) -> Dict:
    try:
        graph = create_graph()
        initial_state = {"query": query, "error": None}
        result = graph.invoke(initial_state)

        if result.get("error"):
            logger.error(f"Workflow failed: {result["error"]}")
            return {"status": "error", "message": result["error"]}

        return {
            "status": "success",
            "filtered_companies": len(result["filtered_corps"]),
            "clusters": len(np.unique(result["clusters"])),
            "quality_metrics": result["qa_result"],
        }

    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}")
        return {"status": "error", "message": str(e)}


def interactive_mode():
    print("Corporate Analysis System")
    print("Enter your queries or 'quit' to exit")
    print("\nExample queries:")
    print("- Find AI companies in Germany")
    print("- Show companies in Berlin clustered by themes")
    print("- Find machine learning startups and cluster by geography")

    while True:
        try:
            query = input("\nEnter query: ").strip()
            if query.lower() == "quit":
                break

            if not query:
                print("Please enter a valid query")
                continue

            result = run_workflow(query)
            print("\nResults:")
            print(json.dumps(result, indent=2))

        except Exception as e:
            print(f"Error: {str(e)}")


if __name__ == "__main__":
    interactive_mode()
