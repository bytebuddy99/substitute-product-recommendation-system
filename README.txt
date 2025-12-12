KG-Based Substitute Product Recommendation System
===========================

Project Title:
KG-Based Substitute Product Recommendation System (Rule-Based Recommender Using Knowledge Graphs)

PROJECT OVERVIEW

This project implements a substitute product recommendation system similar to Flipkart or Amazon grocery substitutions.
When a product is out of stock, the system recommends the best alternative products based on a Knowledge Graph (KG) and rule-based scoring.

The system contains:

A Streamlit user interface for browsing products

A Knowledge Graph representing relationships between products

A rule-based scoring engine for substitution ranking

A product stock editor that saves changes to products.json

No machine learning is used.
The system is fully interpretable, transparent, and designed for academic learning in Responsible AI.

KNOWLEDGE GRAPH DESIGN

The knowledge graph (kg.json) includes:

Nodes:

Product nodes

Category nodes (cat:<name>)

Brand nodes (brand:<name>)

Attribute nodes (tag:<attribute>)

Edges (relations):

IS_A
Meaning: product belongs to a category
Example: p1 --IS_A--> cat:dairy

HAS_BRAND
Meaning: product belongs to a brand
Example: p1 --HAS_BRAND--> brand:Amul

HAS_ATTRIBUTE
Meaning: product has specific tags
Example: p1 --HAS_ATTRIBUTE--> tag:veg

SIMILAR_TO
Meaning: categories are similar or substitutable
Example: cat:dairy --SIMILAR_TO--> cat:dairy_alt

These relations are used to search and score substitute products.

RULE-BASED SCORING SYSTEM

The system ranks substitutes using weighted rules:

Rule Score

Same category + same brand +4
Same category +2
Same brand +1
Similar category +1
Attribute match +1 per match
Cheaper or equal price +1
In stock +2

Hard constraints:

Substitute must be in stock

Must match required attribute tags

Must not exceed maximum price limit (if applied)

PROJECT FILE STRUCTURE

substitute-product-recommendation-system/
│
├
│── app.py (Streamlit UI)
│── logic.py (Recommendation engine + KG processing)
│── rules.py (Rule weights and explanation functions)
│
├
│── products.json (Product dataset)
│── kg.json (Knowledge Graph)
│
├── requirements.txt (Python dependencies)
├── README.txt (This document)
└── other optional files (tests, docs, screenshots)

REQUIREMENTS.TXT

To run the application, install the following dependencies:

streamlit==1.52.1
pandas==2.3.3
networkx==3.6.1
numpy==2.3.5

HOW TO INSTALL AND RUN

Step 1: Create virtual environment
python -m venv venv

Step 2: Activate virtual environment
venv\Scripts\activate (Windows PowerShell)
or
venv\Scripts\activate.bat (CMD)

Step 3: Install dependencies
pip install -r requirements.txt

Step 4: Run the application
streamlit run app.py

Step 5: Open the browser
http://localhost:8501

HOW TO USE THE APPLICATION

Browse product catalog

Grid or table view

Search by name, brand, or category

Filter by category, brand, attribute tags, or stock

Select a product

Product details are displayed

If product is out of stock, substitute suggestions appear

Substitute recommendations

Generated using Knowledge Graph relations and rule scoring

Explanations show why each substitute is recommended

Update product stock

Sidebar stock editor allows changing stock

Save updates products.json

Helpful for testing substitutions

ACADEMIC LEARNING OUTCOMES

The project demonstrates:

Knowledge Graph modeling

Rule-based AI reasoning

JSON dataset design

Streamlit UI development

Explainability in recommendation systems

Modular Python software structure

Suitable for academic courses in:

Responsible AI

AI Systems

Machine Learning Engineering

AI for Society and Humanity

CONCLUSION

This project provides a working, interpretable substitute recommendation system using Knowledge Graphs and rule-based logic.
It delivers a practical implementation of explainable AI suitable for educational and real-world scenarios.