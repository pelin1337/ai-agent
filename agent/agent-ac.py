from typing import Annotated, Sequence
from typing_extensions import TypedDict, List, Dict
import langgraph as lg
from langchain_google_genai import ChatGoogleGenerativeAI, GoogleGenerativeAIEmbeddings
import json
from dotenv import load_dotenv
import os

load_dotenv()

GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

with open("corp_data.json", "r") as f:
    CORP_DATA = json.load(f)


class State(TypedDict):
    query: str
    parsed_query: dict
    filtered_corps: List[Dict]
    clustered_corps: List[Dict]
    qa_result: str


LLM = ChatGoogleGenerativeAI(model="gemini-1.5-flash", google_api_key=GOOGLE_API_KEY)

EMBEDDING = GoogleGenerativeAIEmbeddings(
    model="text-embedding-004", google_api_key=GOOGLE_API_KEY
)


def parse_query(state: State, llm) -> State:
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

    - If the query mentions a grouping criterion not in the list, map it to the closest match.

    Respond only in JSON format with fields `filter` and `group_by`. 
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


def fetch_data(state: State, corp_data: List[Dict]) -> State:
    filter_criteria = state["parsed_query"]["filter"]
    filtered_corps = []
    for corp in corp_data:
        add = True
        for key, value in filter_criteria.items():
            if key == "themes":
                if not set(corp["themes"]).issubset(value):
                    add = False
            else:
                if corp.get(key).lower().find(value.lower()) == -1:
                    add = False
        if add:
            filtered_corps.append(corp)
    return {"filtered_corps": filtered_corps, **state}


def cluster(state: State, embedding) -> State:
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
