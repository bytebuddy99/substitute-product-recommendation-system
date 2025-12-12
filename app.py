# app.py
"""
E-commerce-like Streamlit front-end (no images) with:
 - product catalog (grid / table)
 - advanced sidebar filters
 - product detail pane that shows KG-based substitutes when item is out of stock
 - quick sidebar stock editor (SAVE to products.json only)
Requires (same folder):
 - products.json, kg.json
 - logic.py (exports load_products, load_kg, get_recommendations)
 - rules.py
"""

import os
import json
import tempfile
import math
from typing import List, Dict, Any, Optional

import streamlit as st
import pandas as pd

# logic functions (your logic.py must export these)
from logic import load_products, load_kg, get_recommendations

st.set_page_config(page_title="KG Substitutes — Demo Store", layout="wide")

# ---------- Safe rerun helper (works across Streamlit versions) ----------
def safe_rerun():
    """
    Try to programmatically rerun Streamlit if available.
    Otherwise show a reload button that triggers a browser refresh.
    """
    try:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()
            return
    except Exception:
        pass

    # Fallback UI to prompt the user to reload the page manually
    st.session_state["__reload_needed__"] = not st.session_state.get("__reload_needed__", False)
    st.warning("Changes saved. Click the button below to reload the app and apply changes.")
    if st.button("Reload app (apply changes)"):
        st.markdown("<script>window.location.reload()</script>", unsafe_allow_html=True)
    st.stop()

# ---------- Paths & atomic save helper ----------
BASE_DIR = os.path.dirname(__file__)
PRODUCTS_PATH = os.path.join(BASE_DIR, "products.json")

def save_products_json_atomic(df: pd.DataFrame, path: str = PRODUCTS_PATH) -> None:
    """Atomically save products DataFrame to JSON (UTF-8, pretty)."""
    records = df.to_dict(orient="records")
    tmp_fd, tmp_path = tempfile.mkstemp(suffix=".json", dir=BASE_DIR)
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(records, f, indent=2, ensure_ascii=False)
        os.replace(tmp_path, path)
    except Exception:
        try:
            os.remove(tmp_path)
        except Exception:
            pass
        raise

# ---------- Load data (cached) ----------
@st.cache_data(ttl=600)
def _cached_load():
    df_local = load_products("products.json")
    G_local = load_kg("kg.json")
    return df_local, G_local

# Module-level mutable data used by app
df, G = _cached_load()

# ---------- Sidebar: controls and stock editor (save only) ----------
st.sidebar.header("Controls")

# prefill search if set in session
search_input = st.sidebar.text_input(
    "Search products (name/brand/category)",
    value=st.session_state.get("prefill", ""),
    key="search_input"
)

# prepare lists for filters
_all_categories = sorted([c for c in df["category"].dropna().unique()]) if "category" in df.columns else []
_all_brands = sorted([b for b in df["brand"].dropna().unique()]) if "brand" in df.columns else []
_all_tags = sorted({t for tags in df["tags"].dropna() for t in tags}) if "tags" in df.columns else []

selected_categories = st.sidebar.multiselect("Category", options=_all_categories, default=[])
selected_brands = st.sidebar.multiselect("Brand", options=_all_brands, default=[])
required_tags = st.sidebar.multiselect("Required tags", options=_all_tags, default=[])

in_stock_only = st.sidebar.checkbox("In-stock only", value=False)

max_price_input = st.sidebar.number_input(
    "Max price for substitutes (0 = no limit)",
    min_value=0.0, value=0.0, step=1.0, format="%.2f"
)
max_price_for_subs = None if max_price_input == 0.0 else float(max_price_input)

per_page = st.sidebar.selectbox("Cards per row", [3, 4, 5], index=1)

sort_by = st.sidebar.selectbox("Sort products by", ["name", "price", "stock", "brand", "category"], index=0)

view_mode = st.sidebar.radio("View mode", ["Grid", "Table"], index=0)

if st.sidebar.button("Reset filters"):
    for k in ["prefill", "selected", "search_input", "global_search"]:
        if k in st.session_state:
            del st.session_state[k]
    st.cache_data.clear()
    safe_rerun()

st.sidebar.markdown("---")
st.sidebar.caption("Select a product and change stock. Use Save to persist changes to products.json.")

# Quick stock editor in sidebar (SAVE only)
st.sidebar.subheader("Quick stock editor (save only)")

_prod_options = [f"{row['id']} — {str(row.get('name',''))}" for _, row in df[["id","name"]].iterrows()]
_default_index = st.session_state.get("sidebar_selected_index", 0)
sel = st.sidebar.selectbox("Select product to edit", options=_prod_options, index=_default_index, key="sidebar_sel_product")
st.session_state["sidebar_selected_index"] = _prod_options.index(sel) if sel in _prod_options else 0

sel_id = sel.split(" — ")[0] if sel else None
_current_stock = int(df.loc[df["id"] == sel_id, "stock"].iloc[0]) if sel_id and not df.loc[df["id"] == sel_id].empty else 0

new_stock = st.sidebar.number_input("Stock (set 0 for out-of-stock)", min_value=0, value=_current_stock, step=1, key="sidebar_stock_input")

# Save to disk only (no in-memory-only update)
if st.sidebar.button("Save to products.json", key="sidebar_save_disk"):
    try:
        # coerce types for safety
        if "price" in df.columns:
            df["price"] = pd.to_numeric(df["price"], errors="coerce").fillna(0).astype(float)
        if "stock" in df.columns:
            df["stock"] = pd.to_numeric(df["stock"], errors="coerce").fillna(0).astype(int)
        if sel_id:
            df.loc[df["id"] == sel_id, "stock"] = int(new_stock)
        save_products_json_atomic(df)
        st.success(f"Saved changes to {os.path.basename(PRODUCTS_PATH)}")
        st.cache_data.clear()
        safe_rerun()
    except Exception as e:
        st.error(f"Save failed: {e}")

# ---------- Top search + stats ----------
st.title("Demo Grocery Store — KG Substitutes")
st.write("Browse products; select a product. If it's out of stock, KG-based substitutes will appear in the detail pane.")

col1, col2 = st.columns([3, 1])
with col1:
    query = st.text_input("Search (press Enter to filter)", value=st.session_state.get("global_search",""), key="global_search")
with col2:
    st.metric("Total products", len(df))

# ---------- Apply filters ----------
q_main = (st.session_state.get("global_search") or "").strip()
q_side = (st.session_state.get("search_input") or "").strip()
query_text = q_main or q_side

fdf = df.copy()

# text filter across name/brand/category
if query_text:
    mask = (
        fdf["name"].fillna("").str.contains(query_text, case=False, na=False)
        | fdf["brand"].fillna("").str.contains(query_text, case=False, na=False)
        | fdf["category"].fillna("").str.contains(query_text, case=False, na=False)
    )
    fdf = fdf.loc[mask]

# category filter
if selected_categories:
    fdf = fdf[fdf["category"].isin(selected_categories)]

# brand filter
if selected_brands:
    fdf = fdf[fdf["brand"].isin(selected_brands)]

# required tags
if required_tags:
    def has_all_tags(row):
        tags = row.get("tags") or []
        return all(t in tags for t in required_tags)
    fdf = fdf[fdf.apply(has_all_tags, axis=1)]

# in-stock filter
if in_stock_only:
    fdf = fdf[fdf["stock"].fillna(0).astype(int) > 0]

# sorting
if sort_by:
    if sort_by in ["price", "stock"]:
        fdf = fdf.sort_values(by=sort_by, ascending=True)
    else:
        fdf = fdf.sort_values(by=sort_by, ascending=True, key=lambda s: s.fillna("").astype(str).str.lower())

# store active filters snapshot
st.session_state["active_filters"] = {
    "query": query_text,
    "categories": selected_categories,
    "brands": selected_brands,
    "tags": required_tags,
    "in_stock_only": in_stock_only,
    "sort_by": sort_by
}

# ---------- Catalog helpers ----------
def _product_card_md(prod: dict) -> str:
    name = prod.get("name", "")
    price = prod.get("price", "N/A")
    stock = prod.get("stock", 0)
    brand = prod.get("brand", "")
    tags = prod.get("tags") or []
    tags_txt = ", ".join(tags) if tags else ""
    stock_badge = "🟢 In stock" if stock and int(stock) > 0 else "🔴 Out of stock"
    md = f"**{name}**  \nBrand: {brand}  \nPrice: ₹{price}  \n{stock_badge}  \n{tags_txt}"
    return md

def _render_catalog_grid(df_local: pd.DataFrame, per_row: int = 4):
    records = df_local.to_dict(orient="records")
    if len(records) == 0:
        st.info("No products match the current filters.")
        return
    rows = math.ceil(len(records) / per_row)
    idx = 0
    for _ in range(rows):
        cols = st.columns(per_row)
        for c in cols:
            if idx >= len(records):
                c.empty()
            else:
                prod = records[idx]
                with c:
                    st.markdown(_product_card_md(prod))
                    r1, r2 = st.columns([2, 1])
                    with r1:
                        if st.button("View", key=f"view_{prod['id']}"):
                            st.session_state["selected"] = prod["id"]
                    with r2:
                        if int(prod.get("stock") or 0) > 0:
                            if st.button("Add to cart", key=f"add_{prod['id']}"):
                                st.success(f"Added {prod.get('name')} to cart")
                        else:
                            st.button("Add to cart", key=f"add_{prod['id']}_disabled", disabled=True)
                idx += 1

# ---------- Product detail & substitutes ----------
def _show_product_detail(pid: str, df_local: pd.DataFrame, G_local):
    row = df_local[df_local["id"] == pid]
    if len(row) == 0:
        st.error("Product not found.")
        return
    prod = row.iloc[0].to_dict()
    st.header(prod.get("name"))
    st.write(f"**Brand:** {prod.get('brand') or '—'}")
    st.write(f"**Category:** {prod.get('category') or '—'}")
    st.write(f"**Price:** ₹{prod.get('price')}")
    stock = int(prod.get("stock") or 0)
    if stock > 0:
        st.success(f"In stock — {stock} available")
        if st.button("Add to cart"):
            st.success(f"Added {prod.get('name')} to cart")
    else:
        st.error("Out of stock")
        st.markdown("**Top substitutes (KG-based rule explanations)**")

        recs = get_recommendations(
            prod.get("name") or pid,
            G_local,
            df_local,
            max_results=5,
            max_price=max_price_for_subs,
            required_tags=required_tags if required_tags else None,
            only_in_stock=True
        )

        if len(recs) == 0:
            st.info("No substitutes found.")
        else:
            for r in recs:
                if "error" in r:
                    st.warning(r.get("error"))
                    continue
                st.markdown(f"**{r.get('product_name')}**  — ₹{r.get('price')}  • Stock: {r.get('stock')}  • Score: {r.get('score')}")
                expl = r.get("explanation") or []
                if expl:
                    for line in expl:
                        st.write(f"- {line}")
                c1, c2 = st.columns([3, 1])
                with c1:
                    if st.button("View substitute", key=f"viewsub_{r['product_id']}"):
                        st.session_state["selected"] = r["product_id"]
                with c2:
                    if int(r.get("stock") or 0) > 0:
                        if st.button("Add to cart", key=f"addsub_{r['product_id']}"):
                            st.success(f"Added {r.get('product_name')} to cart")
                    else:
                        st.button("Add to cart", key=f"addsub_{r['product_id']}_disabled", disabled=True)

# ---------- Layout ----------
left, right = st.columns([3, 2])

with left:
    st.subheader("Catalog")
    if view_mode == "Table":
        st.dataframe(fdf[["id", "name", "category", "brand", "price", "stock", "tags"]])
    else:
        _render_catalog_grid(fdf, per_row=per_page)

with right:
    st.subheader("Product detail")
    selected = st.session_state.get("selected")
    if selected:
        _show_product_detail(selected, df, G)
    else:
        st.info("Select a product from the catalog to view details here.")

# Footer: download and filter summary
st.markdown("---")
st.write("Active filters:", st.session_state.get("active_filters"))
st.download_button(
    "Download filtered CSV",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="products_filtered.csv",
    mime="text/csv"
)
