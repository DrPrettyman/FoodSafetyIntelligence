"""
Streamlit app for the EU Food Safety Regulatory Intelligence Engine.

Run with: streamlit run app.py
Requires indexes to be built first: python -m src.pipeline build
"""

import json
import os
from pathlib import Path

import streamlit as st

from src.ingestion.corpus import CATEGORIES, CORPUS
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

# --- Load UI options extracted from the corpus entity index ---

UI_OPTIONS_PATH = Path("data/ui_options.json")

# Groups shown in the form, in display order.
# Each maps to a group key in ui_options.json.
# Primary groups: always visible on form
FORM_GROUPS_PRIMARY = [
    ("product_types", "selectbox"),      # single-select
    ("ingredients", "multiselect"),
    ("product_properties", "multiselect"),
    ("claims", "multiselect"),
    ("packaging", "multiselect"),
    ("commodity_keywords", "multiselect"),
]

# Secondary groups: collapsed under "More options"
FORM_GROUPS_SECONDARY = [
    ("labelling", "multiselect"),
    ("safety", "multiselect"),
    ("production", "multiselect"),
]


def _load_ui_options() -> dict:
    """Load UI options from the extracted JSON file."""
    if UI_OPTIONS_PATH.exists():
        with open(UI_OPTIONS_PATH) as f:
            return json.load(f)
    return {"groups": {}}


UI_OPTIONS = _load_ui_options()

# --- Example scenarios for one-click demo ---

EXAMPLE_SCENARIOS = {
    "Insect protein bar (novel food)": {
        "product_types": "novel food",
        "ingredients": ["food additive", "flavouring substance"],
        "claims": ["health claim"],
        "packaging": ["plastic packaging"],
        "product_properties": ["pre-packaged food"],
        "extra_keywords": "insect protein, whey",
    },
    "Vitamin D supplement": {
        "product_types": "food supplement",
        "ingredients": ["vitamin", "mineral"],
        "claims": ["health claim"],
        "extra_keywords": "vitamin D",
    },
    "Organic infant cereal": {
        "product_types": "infant formula",
        "product_properties": ["organic food"],
        "commodity_keywords": ["processed cereal-based food"],
    },
}


def _regulation_title(celex_id: str) -> str:
    """Look up the human-readable title for a CELEX ID."""
    info = CORPUS.get(celex_id, {})
    return info.get("title", celex_id)


def _eurlex_link(celex_id: str) -> str:
    """Build a EUR-Lex URL for a CELEX ID."""
    return EURLEX_URL.format(celex_id=celex_id)


def _short_title(celex_id: str) -> str:
    """Shortened regulation title for compact display."""
    title = _regulation_title(celex_id)
    # Truncate at first comma or semicolon for readability
    for sep in [" laying down", " on the approximation", " establishing"]:
        if sep in title.lower():
            idx = title.lower().index(sep)
            return title[:idx]
    if len(title) > 120:
        return title[:117] + "..."
    return title


def _check_indexes_exist() -> bool:
    """Check if build indexes exist."""
    return (
        (INDEX_DIR / "defined_terms.json").exists()
        and (INDEX_DIR / "cross_references.json").exists()
        and VECTORSTORE_DIR.exists()
        and (VECTORSTORE_DIR / "embeddings.npy").exists()
    )


def _load_build_stats() -> dict:
    """Load build summary stats."""
    path = INDEX_DIR / "build_summary.json"
    if path.exists():
        with open(path) as f:
            return json.load(f)
    return {}


# --- Page: Welcome ---


def _render_welcome() -> None:
    """Render the welcome / landing screen."""
    st.title("EU Food Safety Regulatory Intelligence")
    st.markdown(
        "Answer EU food compliance questions in seconds. "
        "Select a product scenario below, and the engine will identify applicable "
        "regulations, retrieve relevant articles, and extract structured requirements."
    )

    # Corpus stats
    stats = _load_build_stats()
    if stats:
        cols = st.columns(4)
        cols[0].metric("Regulations", f"{stats.get('regulations', 0):,}")
        cols[1].metric("Articles", f"{stats.get('articles', 0):,}")
        cols[2].metric("Categories", f"{len(CATEGORIES):,}")
        cols[3].metric("Defined terms", f"{stats.get('unique_terms', 0):,}")

    st.markdown("---")

    # Example scenarios
    st.subheader("Quick start")
    st.markdown("Try a pre-built scenario, or configure your own below.")

    example_cols = st.columns(len(EXAMPLE_SCENARIOS))
    for col, (name, scenario) in zip(example_cols, EXAMPLE_SCENARIOS.items()):
        with col:
            if st.button(name, use_container_width=True):
                st.session_state["form_values"] = scenario
                st.session_state["page"] = "form"
                st.rerun()

    st.markdown("")
    if st.button("Configure custom scenario", use_container_width=True):
        st.session_state["page"] = "form"
        st.rerun()


# --- Page: Input form ---


def _render_form_groups(
    form_groups: list[tuple[str, str]],
    groups: dict,
    prefill: dict,
    selections: dict[str, list[str]],
) -> None:
    """Render a list of form groups as selectbox/multiselect widgets."""
    items = []
    for group_key, widget_type in form_groups:
        group_data = groups.get(group_key)
        if not group_data:
            continue
        items.append((group_key, widget_type, group_data))

    i = 0
    while i < len(items):
        group_key, widget_type, group_data = items[i]

        if widget_type == "selectbox":
            options_list = [""] + group_data["options"]
            prefill_val = prefill.get(group_key, "")
            idx = options_list.index(prefill_val) if prefill_val in options_list else 0
            val = st.selectbox(
                group_data["label"],
                options_list,
                index=idx,
                format_func=lambda x, d=group_data: f"Select {d['label'].lower()}..." if x == "" else x.title(),
                help=group_data.get("description", ""),
                key=f"form_{group_key}",
            )
            if val:
                selections[group_key] = [val]
            i += 1
            continue

        # Multiselects: two per row
        batch = items[i:i + 2]
        cols = st.columns(len(batch))
        for col, (gk, _wt, gd) in zip(cols, batch):
            with col:
                prefill_vals = prefill.get(gk, [])
                valid_defaults = [v for v in prefill_vals if v in gd["options"]]
                selected = st.multiselect(
                    gd["label"],
                    gd["options"],
                    default=valid_defaults,
                    help=gd.get("description", ""),
                    key=f"form_{gk}",
                )
                if selected:
                    selections[gk] = selected
        i += len(batch)


def _render_form() -> None:
    """Render the product scenario input form."""
    st.title("Configure product scenario")

    # Back button
    if st.button("\u2190 Back to welcome"):
        st.session_state.pop("form_values", None)
        st.session_state["page"] = "welcome"
        st.rerun()

    st.markdown("---")

    # Load pre-filled values from example scenario (if any)
    prefill = st.session_state.get("form_values", {})
    groups = UI_OPTIONS.get("groups", {})

    # Collect all selected terms across groups
    selections: dict[str, list[str]] = {}
    product_type = ""

    # Render primary form groups
    _render_form_groups(FORM_GROUPS_PRIMARY, groups, prefill, selections)

    # Secondary groups in an expander
    with st.expander("More options (labelling, safety, production)"):
        _render_form_groups(FORM_GROUPS_SECONDARY, groups, prefill, selections)

    # Extract product_type from selections
    if "product_types" in selections:
        product_type = selections["product_types"][0]

    # Free-text keywords for anything not in the dropdowns
    prefill_kw = prefill.get("extra_keywords", "")
    keywords_text = st.text_input(
        "Additional keywords (free text)",
        value=prefill_kw,
        placeholder="e.g. insect protein, whey, CBD",
        help="Comma-separated terms. These are matched against 470 defined terms in the corpus and used for semantic search.",
    )
    extra_keywords = [k.strip() for k in keywords_text.split(",") if k.strip()]

    st.markdown("---")

    # Advanced settings in an expander
    with st.expander("Advanced settings"):
        n_results = st.slider("Articles to retrieve", 5, 30, 10, key="n_results_slider")

        enable_extraction = st.checkbox(
            "Enable LLM extraction",
            help="Adds 10-20s for LLM processing. Without this, you get retrieved articles only (no compliance checklist).",
            key="enable_extraction_cb",
        )

        api_key = None
        provider = "anthropic"
        if enable_extraction:
            provider = st.selectbox(
                "LLM provider",
                ["anthropic", "openai", "claude-code"],
                help="claude-code uses local `claude -p` CLI (no API key needed).",
                key="provider_select",
            )
            if provider != "claude-code":
                env_key = os.environ.get(
                    "ANTHROPIC_API_KEY" if provider == "anthropic" else "OPENAI_API_KEY",
                    "",
                )
                api_key = st.text_input(
                    "API key",
                    value=env_key,
                    type="password",
                    help="Falls back to ANTHROPIC_API_KEY / OPENAI_API_KEY environment variable.",
                    key="api_key_input",
                )

    # Submit
    st.markdown("")
    submitted = st.button(
        "Generate Compliance Report",
        type="primary",
        use_container_width=True,
    )

    if submitted:
        # Flatten all selected terms into pipeline parameters
        all_keywords = []
        for group_key, terms in selections.items():
            if group_key != "product_types":
                all_keywords.extend(terms)
        all_keywords.extend(extra_keywords)

        has_input = product_type or all_keywords
        if not has_input:
            st.warning("Please select at least one product parameter.")
            return

        if enable_extraction and provider != "claude-code" and not api_key:
            st.warning("Please provide an API key for LLM extraction, or disable it.")
            return

        # Map selections to pipeline parameters.
        # product_type → dedicated parameter.
        # ingredients, claims → dedicated parameters.
        # Everything else → keywords (routing table handles all terms).
        ingredients_sel = selections.get("ingredients", [])
        claims_sel = selections.get("claims", [])
        packaging_first = ""
        packaging_rest = []
        if "packaging" in selections:
            packaging_first = selections["packaging"][0]
            packaging_rest = selections["packaging"][1:]
        other_keywords = packaging_rest + [
            t for gk, terms in selections.items()
            if gk not in ("product_types", "ingredients", "claims", "packaging")
            for t in terms
        ] + extra_keywords

        with st.spinner("Analysing regulations..."):
            try:
                result = query(
                    product_type=product_type,
                    ingredients=ingredients_sel or None,
                    claims=claims_sel or None,
                    packaging=packaging_first,
                    keywords=other_keywords or None,
                    n_results=n_results,
                    provider=provider,
                    api_key=api_key if enable_extraction else None,
                    skip_extraction=not enable_extraction,
                )
            except Exception as e:
                st.error(f"Pipeline error: {e}")
                return

        # Build readable params for the banner
        st.session_state["result"] = result
        st.session_state["result_params"] = {
            "product_type": product_type,
            "selections": selections,
            "extra_keywords": extra_keywords,
        }
        st.session_state["page"] = "results"
        st.rerun()


# --- Page: Results ---


def _render_results() -> None:
    """Render the results page."""
    result = st.session_state.get("result")
    params = st.session_state.get("result_params", {})

    if result is None:
        st.session_state["page"] = "welcome"
        st.rerun()
        return

    st.title("Compliance Report")

    # Back / new query
    col_back, col_new = st.columns(2)
    with col_back:
        if st.button("\u2190 Modify scenario"):
            st.session_state["page"] = "form"
            st.rerun()
    with col_new:
        if st.button("New query"):
            st.session_state.pop("result", None)
            st.session_state.pop("result_params", None)
            st.session_state.pop("form_values", None)
            st.session_state["page"] = "welcome"
            st.rerun()

    # Routing summary banner
    _render_routing_banner(result, params)

    st.markdown("---")

    # Tabs for results
    tab_checklist, tab_articles, tab_routing = st.tabs(
        ["Compliance Checklist", "Retrieved Articles", "Routing Detail"]
    )

    with tab_checklist:
        _render_checklist(result)

    with tab_articles:
        _render_articles(result)

    with tab_routing:
        _render_routing(result)


def _render_routing_banner(result: dict, params: dict) -> None:
    """Summary banner showing what was queried and how many regulations matched."""
    routing = result.get("routing", {})
    retrieval = result.get("retrieval", {})
    extraction = result.get("extraction", {})
    xref = routing.get("cross_references", {})

    # Build a human-readable description of the query
    parts = []
    if params.get("product_type"):
        parts.append(f"**{params['product_type'].title()}**")

    selections = params.get("selections", {})
    for gk, terms in selections.items():
        if gk == "product_types":
            continue
        parts.append(", ".join(terms))

    extra_kw = params.get("extra_keywords", [])
    if extra_kw:
        parts.append(", ".join(extra_kw))

    query_desc = " + ".join(parts) if parts else "General query"

    n_regs = routing.get("regulation_count", 0)
    n_xref = xref.get("expanded_count", 0)
    n_core = n_regs - n_xref
    n_articles = retrieval.get("results_count", 0)
    n_requirements = extraction.get("requirements_count", 0)

    st.markdown(f"**Query:** {query_desc}")

    metric_cols = st.columns(4)
    metric_cols[0].metric("Regulations matched", n_core)
    metric_cols[1].metric("Cross-ref expansions", f"+{n_xref}")
    metric_cols[2].metric("Articles retrieved", n_articles)
    if not extraction.get("skipped"):
        metric_cols[3].metric("Requirements extracted", n_requirements)
    else:
        metric_cols[3].metric("LLM extraction", "Disabled")


def _render_checklist(result: dict) -> None:
    """Render the compliance checklist tab."""
    extraction = result.get("extraction", {})

    if extraction.get("skipped"):
        st.info(
            "LLM extraction was not enabled for this query. "
            "Go back and enable it in Advanced Settings to generate a compliance checklist."
        )
        return

    requirements = extraction.get("requirements", [])
    if not requirements:
        st.warning("No requirements were extracted from the retrieved articles.")
        return

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
            reg_title = _short_title(celex)
            summary = req.get("requirement_summary", "")
            req_type = req.get("requirement_type", "").replace("_", " ").title()
            confidence = req.get("confidence", 0)
            eurlex = _eurlex_link(celex)

            with st.expander(f"{summary[:120]}"):
                st.markdown(f"**{req_type}** | Confidence: {confidence:.0%}")
                st.markdown(
                    f"Source: [{reg_title}]({eurlex}) — Article {art_num}"
                    + (f" ({art_title})" if art_title else "")
                )

                if req.get("applicable_to"):
                    st.markdown(f"**Applies to:** {req['applicable_to']}")
                if req.get("conditions"):
                    st.markdown(f"**Conditions:** {req['conditions']}")
                if req.get("source_text_snippet"):
                    st.caption(req["source_text_snippet"][:500])
                if req.get("cross_references"):
                    refs = ", ".join(req["cross_references"])
                    st.markdown(f"**See also:** {refs}")


def _render_articles(result: dict) -> None:
    """Render the retrieved articles tab, grouped by regulation."""
    retrieval = result.get("retrieval", {})
    articles = retrieval.get("articles", [])

    if not articles:
        st.info("No articles were retrieved.")
        return

    # Group by regulation
    by_reg: dict[str, list[dict]] = {}
    for article in articles:
        celex = article.get("metadata", {}).get("celex_id", "unknown")
        by_reg.setdefault(celex, []).append(article)

    st.markdown(
        f"**{len(articles)} articles** from **{len(by_reg)} regulations** "
        f"for query: *\"{retrieval.get('query', '')}\"*"
    )

    for celex, reg_articles in by_reg.items():
        reg_title = _short_title(celex)
        eurlex = _eurlex_link(celex)

        with st.expander(f"{reg_title} ({len(reg_articles)} articles)", expanded=False):
            st.markdown(f"[View on EUR-Lex]({eurlex}) | `{celex}`")

            for article in reg_articles:
                meta = article.get("metadata", {})
                art_num = meta.get("article_number", "?")
                art_title = meta.get("article_title", "")
                score = article.get("score", 0)
                content_type = meta.get("content_type", "article")
                label = "Annex" if content_type == "annex" else f"Art. {art_num}"

                st.markdown(
                    f"**{label}** {art_title} "
                    f"<small style='color: gray;'>relevance: {score:.3f}</small>",
                    unsafe_allow_html=True,
                )
                text = article.get("text", "")
                if text:
                    st.text(text[:1500])
                st.markdown("---")


def _render_routing(result: dict) -> None:
    """Render the routing detail tab."""
    routing = result.get("routing", {})
    celex_ids = routing.get("celex_ids", [])
    reasons = routing.get("reasons", {})
    xref = routing.get("cross_references", {})
    xref_ids = set(xref.get("expanded_celex_ids", []))

    st.markdown(f"**{len(celex_ids)} regulations** selected for search")

    if xref.get("expanded_count", 0) > 0:
        st.markdown(
            f"*{xref['expanded_count']} added via cross-reference expansion "
            f"({xref.get('resolved_refs', 0)} resolved, "
            f"{xref.get('unresolved_refs', 0)} unresolved)*"
        )

    # Split into core vs cross-ref
    core_ids = [c for c in celex_ids if c not in xref_ids]
    xref_list = [c for c in celex_ids if c in xref_ids]

    if core_ids:
        st.markdown("#### Directly routed")
        for celex_id in core_ids:
            reg_title = _short_title(celex_id)
            eurlex = _eurlex_link(celex_id)
            celex_reasons = reasons.get(celex_id, [])
            reason_text = "; ".join(celex_reasons) if celex_reasons else "\u2014"
            st.markdown(f"- [{reg_title}]({eurlex}) `{celex_id}`  \n  {reason_text}")

    if xref_list:
        st.markdown("#### Added via cross-references")
        for celex_id in xref_list:
            reg_title = _short_title(celex_id)
            eurlex = _eurlex_link(celex_id)
            celex_reasons = reasons.get(celex_id, [])
            reason_text = "; ".join(celex_reasons) if celex_reasons else "\u2014"
            st.markdown(f"- [{reg_title}]({eurlex}) `{celex_id}`  \n  {reason_text}")


# --- Main ---


def main() -> None:
    st.set_page_config(
        page_title="EU Food Safety Intelligence",
        page_icon="\U0001f50d",
        layout="centered",
    )

    if not _check_indexes_exist():
        st.error(
            "Indexes not found. Build them first:\n\n"
            "```\npython -m src.pipeline build\n```"
        )
        return

    # Simple page router via session state
    page = st.session_state.get("page", "welcome")

    if page == "welcome":
        _render_welcome()
    elif page == "form":
        _render_form()
    elif page == "results":
        _render_results()
    else:
        st.session_state["page"] = "welcome"
        st.rerun()


if __name__ == "__main__":
    main()
