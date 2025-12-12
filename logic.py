# logic.py
"""
KG-based substitute recommender (no ML).
Exposes:
- load_products(path) -> pandas.DataFrame
- load_kg(path) -> networkx.Graph
- build_kg_from_products(df) -> networkx.Graph  (optional)
- get_recommendations(product_name, G, products_df, ...)
"""

from typing import List, Dict, Any, Optional, Tuple
import os
import json
import math

# external libs
import networkx as nx
import pandas as pd

# import rules (weights + explanation formatter)
from rules import DEFAULT_WEIGHTS, format_explanation

# ---------- Helper: path resolution ----------

def _abs_path(filename: str) -> str:
    """
    Return an absolute path to filename located in the same directory as this module.
    This makes the loader robust to different current working directories.
    """
    base = os.path.dirname(__file__)
    return os.path.join(base, filename)

# ---------- Loading utilities ----------

def load_products(path: str = "products.json") -> pd.DataFrame:
    """Load product catalog saved as JSON array (products.json).
    Uses utf-8-sig encoding to tolerate BOM if present.
    """
    p = _abs_path(path)
    with open(p, "r", encoding="utf-8-sig") as f:
        data = json.load(f)
    df = pd.DataFrame(data)
    for c in ["id", "name", "price", "stock", "tags", "category", "brand"]:
        if c not in df.columns:
            df[c] = None
    return df

def load_kg(path: str = "kg.json") -> nx.Graph:
    """
    Load knowledge graph stored as {nodes:[...], edges:[...]}.
    Edge attribute 'relation' is preserved. Uses utf-8-sig encoding.
    """
    p = _abs_path(path)
    with open(p, "r", encoding="utf-8-sig") as f:
        kg = json.load(f)
    G = nx.Graph()
    # add nodes
    for node in kg.get("nodes", []):
        nid = node["id"]
        attrs = node.copy()
        attrs.pop("id", None)
        G.add_node(nid, **attrs)
    # add edges (store relation; allow multiple relations between same pair)
    for edge in kg.get("edges", []):
        s = edge["source"]
        t = edge["target"]
        rel = edge.get("relation", None)
        if G.has_edge(s, t):
            existing = G[s][t].get("relation")
            if isinstance(existing, list):
                existing.append(rel)
            else:
                # merge into list if existing relation present
                G[s][t]["relation"] = [existing, rel] if existing is not None else [rel]
        else:
            G.add_edge(s, t, relation=rel)
    return G

def build_kg_from_products(df: pd.DataFrame) -> nx.Graph:
    """
    Construct a simple KG from products DataFrame.
    Node ids:
      - products: product id (e.g., "p1")
      - categories: "cat:<name>"
      - brands: "brand:<name>"
      - tags: "tag:<tag>"
    Edges: IS_A, HAS_BRAND, HAS_ATTRIBUTE
    """
    G = nx.Graph()
    for _, row in df.iterrows():
        pid = row["id"]
        G.add_node(pid, type="product", name=row.get("name"), price=row.get("price"), stock=row.get("stock"))
        # category
        cat = row.get("category")
        if pd.notna(cat) and cat:
            cat_node = f"cat:{cat}"
            if not G.has_node(cat_node):
                G.add_node(cat_node, type="category", name=cat)
            G.add_edge(pid, cat_node, relation="IS_A")
        # brand
        brand = row.get("brand")
        if pd.notna(brand) and brand:
            brand_node = f"brand:{brand}"
            if not G.has_node(brand_node):
                G.add_node(brand_node, type="brand", name=brand)
            G.add_edge(pid, brand_node, relation="HAS_BRAND")
        # tags / attributes
        tags = row.get("tags") or []
        for t in tags:
            tag_node = f"tag:{t}"
            if not G.has_node(tag_node):
                G.add_node(tag_node, type="attribute", name=t)
            G.add_edge(pid, tag_node, relation="HAS_ATTRIBUTE")
    return G

# ---------- Search & helpers ----------

def _find_product_id_by_name(df: pd.DataFrame, query: str) -> Optional[str]:
    """Case-insensitive substring match. Returns first matched product id or None."""
    if not query:
        return None
    mask = df["name"].fillna("").str.contains(query, case=False, na=False)
    if mask.any():
        return str(df.loc[mask].iloc[0]["id"])
    mask2 = df["id"].astype(str) == query
    if mask2.any():
        return str(df.loc[mask2].iloc[0]["id"])
    return None

def _gather_candidates(G: nx.Graph, product_id: str) -> List[str]:
    """
    Gather candidate product ids exploring:
      - same category (via IS_A)
      - same brand (via HAS_BRAND)
      - attributes (via HAS_ATTRIBUTE)
      - similar categories (via SIMILAR_TO)
    """
    candidates = set()
    if product_id not in G:
        return []
    for nbr in G.neighbors(product_id):
        ntype = G.nodes[nbr].get("type")
        if ntype == "category":
            # products in same category
            for p in G.neighbors(nbr):
                if G.nodes[p].get("type") == "product":
                    candidates.add(p)
            # similar categories (SIMILAR_TO)
            for cat2 in G.neighbors(nbr):
                # skip products and original node
                if cat2 != product_id and G.nodes[cat2].get("type") == "category":
                    edge_rel = G[nbr][cat2].get("relation")
                    if (isinstance(edge_rel, list) and "SIMILAR_TO" in edge_rel) or edge_rel == "SIMILAR_TO":
                        for p2 in G.neighbors(cat2):
                            if G.nodes[p2].get("type") == "product":
                                candidates.add(p2)
        elif ntype == "brand":
            for p in G.neighbors(nbr):
                if G.nodes[p].get("type") == "product":
                    candidates.add(p)
        elif ntype == "attribute":
            for p in G.neighbors(nbr):
                if G.nodes[p].get("type") == "product":
                    candidates.add(p)
        else:
            # direct product neighbor
            if G.nodes[nbr].get("type") == "product":
                candidates.add(nbr)
    return list(candidates)

# ---------- Scoring ----------

def _score_candidate(G: nx.Graph,
                     orig_pid: str,
                     cand_pid: str,
                     products_df: pd.DataFrame,
                     weights: Dict[str, int],
                     required_tags: Optional[List[str]] = None,
                     max_price: Optional[float] = None) -> Tuple[int, List[str]]:
    """
    Compute score and return (score, fired_rule_keys).
    Uses sentinel negative returns for hard-constraint failures.
    """
    score = 0
    fired: List[str] = []
    if orig_pid == cand_pid:
        return -9999, ["same_product"]

    def _get_meta(pid, key):
        val = G.nodes[pid].get(key)
        if val is None:
            row = products_df[products_df["id"] == pid]
            if len(row) > 0:
                val = row.iloc[0].get(key)
        return val

    # category and brand lists
    orig_cats = [n for n in G.neighbors(orig_pid) if G.nodes[n].get("type") == "category"]
    cand_cats = [n for n in G.neighbors(cand_pid) if G.nodes[n].get("type") == "category"]
    orig_brands = [n for n in G.neighbors(orig_pid) if G.nodes[n].get("type") == "brand"]
    cand_brands = [n for n in G.neighbors(cand_pid) if G.nodes[n].get("type") == "brand"]

    same_cat = any(c in cand_cats for c in orig_cats)
    same_brand = any(b in cand_brands for b in orig_brands)
    if same_cat and same_brand:
        score += weights.get("same_category_same_brand", 4)
        fired.append("same_category_same_brand")
    if same_cat and not same_brand:
        score += weights.get("same_category", 2)
        fired.append("same_category")
    if same_brand and not same_cat:
        score += weights.get("same_brand", 1)
        fired.append("same_brand")

    # similar category check
    for oc in orig_cats:
        for cc in cand_cats:
            if G.has_edge(oc, cc):
                rel = G[oc][cc].get("relation")
                if (isinstance(rel, list) and "SIMILAR_TO" in rel) or rel == "SIMILAR_TO":
                    score += weights.get("similar_category", 1)
                    fired.append("similar_category")
                    break

    # attribute matches
    orig_attrs = {n for n in G.neighbors(orig_pid) if G.nodes[n].get("type") == "attribute"}
    cand_attrs = {n for n in G.neighbors(cand_pid) if G.nodes[n].get("type") == "attribute"}
    common_attrs = orig_attrs.intersection(cand_attrs)
    if common_attrs:
        amt = len(common_attrs)
        score += amt * weights.get("attribute_match", 1)
        fired.append(f"attribute_match({amt})")

    # required tags (hard constraint)
    if required_tags:
        missing_required = []
        for rt in required_tags:
            tag_node = f"tag:{rt}"
            if tag_node not in cand_attrs:
                missing_required.append(rt)
        if missing_required:
            return -9998, [f"missing_required_tags:{missing_required}"]

    # price comparisons
    try:
        orig_price = float(_get_meta(orig_pid, "price") or math.nan)
        cand_price = float(_get_meta(cand_pid, "price") or math.nan)
    except Exception:
        orig_price = math.nan
        cand_price = math.nan
    if not math.isnan(orig_price) and not math.isnan(cand_price):
        if cand_price <= orig_price:
            score += weights.get("cheaper_bonus", 1)
            fired.append("cheaper_or_equal")

    # max_price hard filter
    if max_price is not None:
        try:
            if cand_price > float(max_price):
                return -9997, [f"exceeds_max_price:{cand_price}"]
        except Exception:
            pass

    # stock check
    try:
        cand_stock = int(_get_meta(cand_pid, "stock") or 0)
    except Exception:
        cand_stock = 0
    if cand_stock > 0:
        score += weights.get("in_stock_bonus", 2)
        fired.append("in_stock")
    else:
        return -9996, ["out_of_stock"]

    return score, fired

# ---------- Public API: get_recommendations ----------

def get_recommendations(product_name: str,
                        G: nx.Graph,
                        products_df: pd.DataFrame,
                        max_results: int = 3,
                        max_price: Optional[float] = None,
                        required_tags: Optional[List[str]] = None,
                        only_in_stock: bool = True,
                        weights: Optional[Dict[str, int]] = None) -> List[Dict[str, Any]]:
    """
    Return ranked substitutes with explanations.
    """
    if weights is None:
        weights = DEFAULT_WEIGHTS

    pid = _find_product_id_by_name(products_df, product_name)
    if pid is None:
        return [{"error": "product_not_found", "query": product_name}]

    row = products_df[products_df["id"] == pid]
    orig_stock = int(row.iloc[0].get("stock") or 0) if len(row) > 0 else 0
    # default behavior: when original is in stock, present original (caller can override)
    if orig_stock > 0 and only_in_stock:
        return [{"product_id": pid,
                 "product_name": G.nodes[pid].get("name") or (row.iloc[0].get("name") if len(row)>0 else pid),
                 "score": None,
                 "explanation": ["Original product is in stock"],
                 "path": [pid]}]

    candidates = _gather_candidates(G, pid)
    candidates = [c for c in candidates if c != pid]
    candidates = list(dict.fromkeys(candidates))  # preserve order, dedupe

    scored = []
    for cand in candidates:
        s, fired = _score_candidate(G, pid, cand, products_df, weights, required_tags, max_price)
        if s is None:
            continue
        if isinstance(s, int) and s < 0:
            continue
        explanation_lines = format_explanation(fired)
        pname = G.nodes[cand].get("name") or (products_df[products_df["id"] == cand].iloc[0].get("name") if len(products_df[products_df["id"] == cand])>0 else cand)
        pmeta = products_df[products_df["id"] == cand]
        price = None
        stock = None
        if len(pmeta) > 0:
            price = pmeta.iloc[0].get("price")
            stock = pmeta.iloc[0].get("stock")
        path = []
        if fired and ("same_category_same_brand" in fired or "same_category" in fired or "similar_category" in fired):
            try:
                shared_cat = None
                for c in G.neighbors(pid):
                    if G.nodes[c].get("type") == "category" and G.has_edge(c, cand):
                        shared_cat = c
                        break
                if shared_cat:
                    path = [pid, shared_cat, cand]
                else:
                    for b in G.neighbors(pid):
                        if G.nodes[b].get("type") == "brand" and G.has_edge(b, cand):
                            path = [pid, b, cand]
                            break
            except Exception:
                path = []
        scored.append({
            "product_id": cand,
            "product_name": pname,
            "score": s,
            "explanation": explanation_lines,
            "price": price,
            "stock": stock,
            "path": path
        })

    def _sort_key(x):
        score = x.get("score") or 0
        price = x.get("price")
        price_key = -(price or 0)
        return (score, price_key, x.get("product_name") or "")

    scored_sorted = sorted(scored, key=_sort_key, reverse=True)
    return scored_sorted[:max_results]

# Demo
if __name__ == "__main__":
    print("Demo: loading products.json and kg.json")
    df = load_products("products.json")
    G = load_kg("kg.json")
    q = "Amul Full Cream Milk"
    print(f"\nQuery: {q}")
    recs = get_recommendations(q, G, df, max_results=5, required_tags=None, only_in_stock=False)
    for r in recs:
        print(f"- {r['product_name']} (id={r['product_id']}) score={r['score']}")
        print("  explanation:", "; ".join(r['explanation']))
        if r['path']:
            print("  path:", " -> ".join(r['path']))
