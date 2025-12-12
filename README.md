# substitute-product-recommendation-system
knowledge graph based substitute product recomendation system
## 🚀 Live Demo

The application is deployed here:

👉 https://kg-sub-system99.streamlit.app/


  📌 KG-Based Substitute Product Recommendation System
(Rule-Based Recommender Using Knowledge Graphs)
📝 Project Overview

This project implements a substitute product recommendation system inspired by platforms like Flipkart and Amazon Grocery.
When a product becomes out of stock, the system automatically recommends the best alternative products using:

A Knowledge Graph (KG)

A rule-based scoring engine

A clean and interactive Streamlit UI

No machine learning is required—every recommendation is fully interpretable, transparent, and designed for educational purposes in Responsible & Ethical AI.

🔗 Knowledge Graph Design

The Knowledge Graph (kg.json) represents semantic relationships between products and their attributes.

🟦 Node Types
Node Type	Prefix	Example
Product	(none)	p1, p2, p3
Category	cat:	cat:dairy
Brand	brand:	brand:Amul
Attribute Tag	tag:	tag:veg, tag:lactose_free=yes
🟩 Relations Used in the KG
1️⃣ IS_A

Product → Category

p1 --IS_A--> cat:dairy

2️⃣ HAS_BRAND

Product → Brand

p1 --HAS_BRAND--> brand:Amul

3️⃣ HAS_ATTRIBUTE

Product → Attribute tags

p1 --HAS_ATTRIBUTE--> tag:veg

4️⃣ SIMILAR_TO

Category ↔ Category

cat:dairy --SIMILAR_TO--> cat:dairy_alt


These relations help the engine identify potential substitutes through category similarity, brand match, or shared attributes.

🧠 Rule-Based Scoring System

Substitute products are ranked using a transparent, explainable rule engine.

🔢 Scoring Rules
Rule Condition	Score
Same category & same brand	+4
Same category	+2
Same brand	+1
Similar category	+1
Attribute match	+1 per attribute
Cheaper or equal price	+1
Product in stock	+2
❗ Hard Constraints

A candidate is rejected if:

It is out of stock

It lacks the required attribute tags

It exceeds a specified maximum price

This ensures reliable, shopper-friendly substitution recommendations.

📁 Project Structure
substitute-product-recommendation-system/
│
├── app.py               # Streamlit user interface
├── logic.py             # KG processing + scoring engine
├── rules.py             # Rule weights + explanation formatting
│
├── products.json        # Product dataset
├── kg.json              # Knowledge Graph file
│
├── requirements.txt     # Python dependencies
├── README.md            # Documentation
└── (optional) docs/, screenshots/, tests/


📦 requirements.txt

Install these dependencies before running the project:

streamlit==1.52.1
pandas==2.3.3
networkx==3.6.1
numpy==2.3.5

🚀 How to Install & Run
1️⃣ Create a virtual environment
python -m venv venv

2️⃣ Activate the environment

PowerShell:

venv\Scripts\activate


CMD:

venv\Scripts\activate.bat

3️⃣ Install dependencies
pip install -r requirements.txt

4️⃣ Run the Streamlit app
streamlit run app.py

5️⃣ Open the local app
http://localhost:8501

🖥️ How to Use the Application
✔️ Browse Product Catalog

View products in grid/table format with price, stock, category, and brand.

✔️ Search Products

Find products by name, brand, or category.

✔️ View Product Details

If the product is in stock, details are shown normally.
If out of stock, substitute recommendations appear.

✔️ Substitute Recommendations

Generated using:

Knowledge Graph traversal

Rule scoring

Attribute matching

Price constraints

Stock availability

Each recommendation is accompanied by a clear explanation.

✔️ Update Product Stock

The sidebar contains a stock editor:

Select any product

Change its stock

Save → updates products.json on disk

Automatically refreshes recommendations

This feature helps test substitution logic for any product.
