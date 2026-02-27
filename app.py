"""
Streamlit app for the EU Food Safety Regulatory Intelligence Engine.

Run with: streamlit run app.py
Requires indexes to be built first: python -m src.pipeline build
"""

import os
from pathlib import Path

import streamlit as st

from src.ingestion.corpus import CORPUS
from src.pipeline import INDEX_DIR, VECTORSTORE_DIR, query

EURLEX_URL = "https://eur-lex.europa.eu/legal-content/EN/ALL/?uri=CELEX:{celex_id}"

PRIORITY_LABELS = {
    "before_launch": "Before Launch",
    "ongoing": "Ongoing Obligations",
    "if_applicable": "If Applicable",
}

PRIORITY_ICONS = {
    "before_launch": "\u26a0\ufe0f",
    "ongoing": "\U0001f504",
    "if_applicable": "\u2139\ufe0f",
}

PRODUCT_TYPES = [
    "",
    "novel food",
    "food supplement",
    "infant formula",
    "food for special medical purposes",
    "organic food",
]

INGREDIENT_OPTIONS = [
    "food additive",
    "flavouring",
    "food enzyme",
    "gmo",
    "vitamin",
    "mineral",
]

CLAIM_OPTIONS = [
    "health claim",
    "nutrition claim",
]

PACKAGING_OPTIONS = [
    "",
    "plastic packaging",
    "food contact material",
]


def _regulation_title(celex_id: str) -> str:
    """Look up the human-readable title for a CELEX ID."""
    info = CORPUS.get(celex_id, {})
    return info.get("title", celex_id)


def _eurlex_link(celex_id: str) -> str:
    """Build a EUR-Lex URL for a CELEX ID."""
    return EURLEX_URL.format(celex_id=celex_id)


def _check_indexes_exist() -> bool:
    """Check if build indexes exist."""
    return (
        (INDEX_DIR / "defined_terms.json").exists()
        and (INDEX_DIR / "cross_references.json").exists()
        and VECTORSTORE_DIR.exists()
        and (VECTORSTORE_DIR / "embeddings.npy").exists()
    )


def _render_sidebar() -> dict:
    """Render the sidebar input form and return parameters."""
    st.sidebar.title("EU Food Safety Regulatory Intelligence")
    st.sidebar.markdown("---")

    product_type = st.sidebar.selectbox(
        "Product category",
        PRODUCT_TYPES,
        format_func=lambda x: "Select a product category..." if x == "" else x.title(),
    )

    ingredients = st.sidebar.multiselect("Ingredients", INGREDIENT_OPTIONS)

    claims = st.sidebar.multiselect("Claims", CLAIM_OPTIONS)

    packaging = st.sidebar.selectbox(
        "Packaging type",
        PACKAGING_OPTIONS,
        format_func=lambda x: "None selected" if x == "" else x.title(),
    )

    keywords_text = st.sidebar.text_input(
        "Additional keywords",
        placeholder="e.g. insect protein, whey",
    )
    keywords = [k.strip() for k in keywords_text.split(",") if k.strip()] or None

    st.sidebar.markdown("---")
    n_results = st.sidebar.slider("Articles to retrieve", 5, 30, 10)

    enable_extraction = st.sidebar.checkbox(
        "Enable LLM extraction",
        help="Requires an API key (or claude-code installed locally). Adds 10-20s for LLM processing.",
    )

    api_key = None
    provider = "anthropic"
    if enable_extraction:
        provider = st.sidebar.selectbox(
            "LLM provider",
            ["anthropic", "openai", "claude-code"],
            help="claude-code uses local `claude -p` CLI (no API key needed).",
        )
        if provider != "claude-code":
            env_key = os.environ.get(
                "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY",
                "",
            )
            api_key = st.sidebar.text_input(
                "API key",
                value=env_key,
                type="password",
                help="Falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY environment variable.",
            )

    return {
        "product_type": product_type,
        "ingredients": ingredients or None,
        "claims": claims or None,
        "packaging": packaging,
        "keywords": keywords,
        "n_results": n_results,
        "enable_extraction": enable_extraction,
        "api_key": api_key,
        "provider": provider,
    }


def _render_checklist(result: dict) -> None:
    """Render the compliance checklist tab."""
    extraction = result.get("extraction", {})

    if extraction.get("skipped"):
        st.info(
            "LLM extraction is disabled. Enable it in the sidebar to generate a compliance checklist."
        )
        return

    requirements = extraction.get("requirements", [])
    if not requirements:
        st.warning("No requirements were extracted from the retrieved articles.")
        return

    st.markdown(
        f"**{len(requirements)} compliance requirements** extracted "
        f"from {extraction.get('articles_processed', '?')} articles"
    )

    # Group by priority
    groups: dict[str, list[dict]] = {}
    for req in requirements:
        priority = req.get("priority", "if_applicable")
        groups.setdefault(priority, []).append(req)

    for priority_key in ["before_launch", "ongoing", "if_applicable"]:
        reqs = groups.get(priority_key, [])
        if not reqs:
            continue

        icon = PRIORITY_ICONS.get(priority_key, "")
        label = PRIORITY_LABELS.get(priority_key, priority_key)
        st.markdown(f"### {icon} {label} ({len(reqs)})")

        for req in reqs:
            celex = req.get("regulation_id", "?")
            art_num = req.get("article_number", "?")
            art_title = req.get("article_title", "")
            reg_title = _regulation_title(celex)
            summary = req.get("requirement_summary", "")
            req_type = req.get("requirement_type", "").replace("_", " ").title()
            confidence = req.get("confidence", 0)
            eurlex = _eurlex_link(celex)

            header = f"**{summary[:100]}**" if len(summary) > 100 else f"**{summary}**"

            with st.expander(f"{req_type} — {reg_title} Art. {art_num}"):
                st.markdown(header)

                col1, col2 = st.columns(2)
                with col1:
                    st.markdown(f"**Type:** {req_type}")
                    st.markdown(
                        f"**Source:** [{reg_title}]({eurlex}) Art. {art_num}"
                    )
                with col2:
                    st.markdown(f"**Confidence:** {confidence:.0%}")
                    if art_title:
                        st.markdown(f"**Article:** {art_title}")

                if req.get("applicable_to"):
                    st.markdown(f"**Applies to:** {req['applicable_to']}")
                if req.get("conditions"):
                    st.markdown(f"**Conditions:** {req['conditions']}")
                if req.get("source_text_snippet"):
                    st.markdown(f"> {req['source_text_snippet']}")
                if req.get("cross_references"):
                    refs = ", ".join(req["cross_references"])
                    st.markdown(f"**Cross-references:** {refs}")


def _render_articles(result: dict) -> None:
    """Render the retrieved articles tab."""
    retrieval = result.get("retrieval", {})
    articles = retrieval.get("articles", [])

    st.markdown(
        f"**{len(articles)} articles** retrieved for query: "
        f"*\"{retrieval.get('query', '')}\"*"
    )

    for i, article in enumerate(articles, 1):
        meta = article.get("metadata", {})
        celex = meta.get("celex_id", "?")
        art_num = meta.get("article_number", "?")
        art_title = meta.get("article_title", "")
        score = article.get("score", 0)
        reg_title = _regulation_title(celex)
        eurlex = _eurlex_link(celex)

        with st.expander(
            f"{i}. [{reg_title}]  Art. {art_num} — {art_title}  "
            f"(relevance: {score:.3f})"
        ):
            st.markdown(
                f"**Source:** [{reg_title}]({eurlex}) | "
                f"**Article {art_num}:** {art_title} | "
                f"**Score:** {score:.3f}"
            )
            text = article.get("text", "")
            if text:
                st.text(text[:2000])


def _render_routing(result: dict) -> None:
    """Render the routing transparency tab."""
    routing = result.get("routing", {})
    celex_ids = routing.get("celex_ids", [])
    reasons = routing.get("reasons", {})
    xref = routing.get("cross_references", {})

    st.markdown(f"**{len(celex_ids)} regulations** selected for search")

    if xref.get("expanded_count", 0) > 0:
        st.markdown(
            f"*{xref['expanded_count']} added via cross-reference expansion "
            f"({xref.get('resolved_refs', 0)} resolved, "
            f"{xref.get('unresolved_refs', 0)} unresolved)*"
        )

    for celex_id in celex_ids:
        reg_title = _regulation_title(celex_id)
        eurlex = _eurlex_link(celex_id)
        celex_reasons = reasons.get(celex_id, [])
        reason_text = "; ".join(celex_reasons) if celex_reasons else "—"

        st.markdown(f"- **[{reg_title}]({eurlex})** (`{celex_id}`): {reason_text}")


def main() -> None:
    st.set_page_config(
        page_title="EU Food Safety Intelligence",
        page_icon="\U0001f50d",
        layout="wide",
    )

    if not _check_indexes_exist():
        st.error(
            "Indexes not found. Build them first:\n\n"
            "```\npython -m src.pipeline build\n```"
        )
        return

    params = _render_sidebar()

    # Generate button in sidebar
    run_query = st.sidebar.button(
        "Generate Compliance Checklist",
        type="primary",
        use_container_width=True,
    )

    if run_query:
        # Validate inputs
        has_input = (
            params["product_type"]
            or params["ingredients"]
            or params["claims"]
            or params["packaging"]
            or params["keywords"]
        )
        if not has_input:
            st.warning("Please select at least one product parameter.")
            return

        if (
            params["enable_extraction"]
            and params["provider"] != "claude-code"
            and not params["api_key"]
        ):
            st.warning("Please provide an API key for LLM extraction, or disable it.")
            return

        with st.spinner("Querying pipeline..."):
            try:
                result = query(
                    product_type=params["product_type"],
                    ingredients=params["ingredients"],
                    claims=params["claims"],
                    packaging=params["packaging"],
                    keywords=params["keywords"],
                    n_results=params["n_results"],
                    provider=params["provider"],
                    api_key=params["api_key"] if params["enable_extraction"] else None,
                    skip_extraction=not params["enable_extraction"],
                )
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                return

        st.session_state["result"] = result

    # Display results if available
    result = st.session_state.get("result")
    if result is None:
        st.markdown("## EU Food Safety Regulatory Intelligence Engine")
        st.markdown(
            "Select product parameters in the sidebar and click "
            "**Generate Compliance Checklist** to get started."
        )
        return

    tab_checklist, tab_articles, tab_routing = st.tabs(
        ["Compliance Checklist", "Retrieved Articles", "Routing"]
    )

    with tab_checklist:
        _render_checklist(result)

    with tab_articles:
        _render_articles(result)

    with tab_routing:
        _render_routing(result)


if __name__ == "__main__":
    main()
