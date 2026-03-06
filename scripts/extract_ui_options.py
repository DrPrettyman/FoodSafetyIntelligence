"""
Extract UI dropdown options from the entity index and corpus.

Reads the defined terms index and CATEGORY_ROUTING to produce a curated
JSON file of options for the Streamlit app, grouped into UI-friendly
categories:

  - product_types: what the product IS (novel food, supplement, infant formula...)
  - ingredients: what's IN the product (additives, flavourings, enzymes, vitamins...)
  - product_properties: characteristics (organic, GMO, irradiated...)
  - claims: marketing claims (health claim, nutrition claim...)
  - packaging: packaging materials (plastic, food contact material...)
  - safety: contaminants, controls, labelling concepts
  - commodity_keywords: product-standard commodities (honey, cocoa, sugar...)

Each option has: term (display label), routing_key (matches CATEGORY_ROUTING or
defined-term routing), source (where it came from), and category (corpus category).

Usage:
    python -m scripts.extract_ui_options
"""

import json
from pathlib import Path

from src.ingestion.corpus import CATEGORIES, CORPUS
from src.pipeline import load_entity_index
from src.retrieval.routing import CATEGORY_ROUTING

OUTPUT_PATH = Path("data/ui_options.json")

# --- Classification rules ---
# Map corpus categories to UI groups
CATEGORY_TO_UI_GROUP = {
    "novel_food": "product_types",
    "food_specific_groups": "product_types",
    "food_supplements": "product_types",
    "food_additives": "ingredients",
    "flavourings": "ingredients",
    "food_enzymes": "ingredients",
    "fortification": "ingredients",
    "gmo": "product_properties",
    "organic": "product_properties",
    "food_irradiation": "product_properties",
    "food_contact_materials": "packaging",
    "nutrition_health_claims": "claims",
    "labelling_fic": "labelling",
    "contaminants": "safety",
    "official_controls": "safety",
    "general_food_law": "general",
    "feed": "other",
    "product_standards": "commodity_keywords",
}

# Terms to exclude: too generic, procedural, or not useful for product description
EXCLUDE_TERMS = {
    # Too generic
    "food", "feed", "ingredient", "product", "operator", "business",
    "business operator", "competent authority", "authority", "file",
    "request", "notification", "application", "placing on the market",
    "final consumer", "retail", "risk", "risk analysis", "risk assessment",
    "risk communication", "risk management", "hazard", "processing",
    "preparation", "labelling", "batch", "restriction", "specification",
    "advertising", "traceability", "the applicant", "recipient member state",
    "exporter", "importer", "import", "export", "party", "non-party",
    "secretariat", "the bch", "the protocol", "source material",
    "consultation request",
    # Internal/procedural
    "quality assurance system", "quality control system", "proficiency test",
    "control sample", "full validation procedure", "good manufacturing practice (gmp)",
    "manufacturing stage", "converter", "challenge test", "unit operation",
    "decontamination installation", "decontamination process",
    "decontamination technology", "recycler", "recycling facility",
    "recycling installation", "recycling process", "recycling scheme",
    "recycling technology", "reprocessing of plastic", "pre-processing",
    "post-processing", "original dossier", "interested business operator",
    "scf guidelines of 1992", "food-contact side", "non-food-contact side",
    "food simulant", "aid to polymerisation", "polymer production aid",
    "intermediate food contact materials", "final food contact articles",
    "hot-fill", "non-intentionally added substance",
    "overall migration limit", "specific migration limit",
    # Duplicates of routing keys (keep the routing key version)
    "flavourings", "food additive", "novel food",
    # Admin/governance from organic
    "control authority", "control body", "competent authorities",
    "non-compliance", "precautionary measures", "preventive measures",
    "stage of production, preparation and distribution",
    # Admin from official controls (mostly procedural)
    "aac network", "adis", "adis network", "advanced electronic seal",
    "advanced electronic signature", "alert and cooperation network",
    "alert notification",
    # Official controls — exclude all by default (230 mostly procedural/veterinary terms).
    # Useful ones are added via FORCE_GROUP below.
}

# All official_controls terms excluded, then selectively re-included via FORCE_GROUP
_OC_ALLOW = {
    "animal by-products", "bivalve molluscs", "composite product",
    "fishery products", "fresh meat", "gelatin", "live animals",
    "meat preparations", "mechanically separated meat", "minced meat",
    "milk", "raw milk", "rendered fats", "treated stomachs",
    "wild game", "poultry meat", "collagen", "colostrum",
}

EXCLUDE_TERMS |= {
    # GMO procedural terms
    "biological diversity", "contained use", "conventional counterpart",
    "deliberate release", "developing countries", "focal point",
    "non-party", "organism", "transboundary movement", "unique identifier",
    # Organic procedural/farming terms too specific for product input
    "equivalence", "non-compliance", "conversion", "in-conversion product",
    "non-organic production unit", "organic production unit",
    "organic heterogeneous material", "production unit", "production cycle",
    "soil-related crop cultivation", "usable area", "veranda",
    "energy from renewable sources", "locally grown species", "generation",
    "mother plant", "plant reproductive material", "pullets",
    "poultry house", "laying hens", "hatchery", "nursery",
    # General food law terms too abstract for UI
    "equivalent", "establishment", "sufficient",
    # Food contact materials terms too technical
    "component", "polymer", "plastic input",
    "product loops which are in a closed and controlled chain",
    "hazardous bisphenol or hazardous bisphenol derivative",
    "non-fatty food",
    # Organic duplicates/procedural
    "in-conversion production unit",
    "the first stage of the placing on the market of a product",
    # Duplicate concepts (keep shorter version)
    "pre-packaged product", "prepacked food",  # keep "pre-packaged food"
    # Ingredients too niche
    "appropriate physical process", "quantum satis", "functional class",
    "monomer or other starting substance", "uvcb substance",
    "biodynamic preparations", "other substance",
    # General too abstract
    "feed business", "feed business operator", "food business",
    "food business operator", "food law",
    # Labelling too technical for input
    "field of vision", "principal field of vision", "legibility",
    "means of distance communication", "food information law",
    "food information", "trimmings",
    # Safety too technical
    "critical gap", "limit of determination", "benchmark levels",
    # Production too niche
    "agricultural area", "agricultural raw material", "usable area",
    "polyculture", "water pollution",
    # Very long compound terms that won't fit UI well
    "stages of production, processing and distribution",
    "history of safe food use in a third country",
    "status of qualified presumption of safety",
    "gmo containing a single transformation event",
    "gmo containing stacked transformation events",
    "genetically modified organism for feed use",
    "genetically modified organism for food use",
    "date of minimum durability of a food",
    "food ingredient with flavouring properties",
    "active food contact materials and articles",
    "intelligent food contact materials and articles",
    "foodstuffs for people intolerant to gluten",
    "closed recirculation aquaculture facility",
    "organic variety suitable for organic production",
    "integrity of organic or in-conversion products",
    "small and medium-sized enterprise (sme)",
}

# Terms to force into specific UI groups (override category-based assignment)
FORCE_GROUP = {
    # Product types (from various categories)
    "baby food": "product_types",
    "infant formula": "product_types",
    "follow-on formula": "product_types",
    "processed cereal-based food": "product_types",
    "food for special medical purposes": "product_types",
    "total diet replacement for weight control": "product_types",
    "traditional food from a third country": "product_types",
    "novel food": "product_types",
    # Ingredients
    "food additive": "ingredients",
    "approved food additive": "ingredients",
    "processing aid": "ingredients",
    "table-top sweeteners": "ingredients",
    "flavouring substance": "ingredients",
    "natural flavouring substance": "ingredients",
    "smoke flavouring": "ingredients",
    "thermal process flavouring": "ingredients",
    "flavour precursor": "ingredients",
    "flavouring preparation": "ingredients",
    "other flavouring": "ingredients",
    "engineered nanomaterial": "ingredients",
    "additive": "ingredients",
    "monomer or other starting substance": "ingredients",
    "other substance": "ingredients",
    "bisphenol": "ingredients",
    "bisphenol derivative": "ingredients",
    "uvcb substance": "ingredients",
    "feed additives": "ingredients",
    "feed materials": "ingredients",
    "biodynamic preparations": "ingredients",
    "plant protection products": "ingredients",
    "veterinary medicinal product": "ingredients",
    # Product properties
    "organic product": "product_properties",
    "in-conversion product": "product_properties",
    "genetically modified food": "product_properties",
    "genetically modified feed": "product_properties",
    "produced from gmos": "product_properties",
    "produced by gmos": "product_properties",
    "pre-packaged food": "product_properties",
    "prepacked food": "product_properties",
    "energy-reduced food": "product_properties",
    "food with no added sugars": "product_properties",
    "unprocessed food": "product_properties",
    "processed products": "product_properties",
    "unprocessed products": "product_properties",
    "minor food": "product_properties",
    # Packaging
    "plastic": "packaging",
    "plastic materials and articles": "packaging",
    "recycled plastic": "packaging",
    "recycled plastic materials and articles": "packaging",
    "active materials and articles": "packaging",
    "intelligent materials and articles": "packaging",
    "multi-material multi-layer": "packaging",
    "plastic multi-layer": "packaging",
    "functional barrier": "packaging",
    "hermetically sealed container": "packaging",
    "packaging": "packaging",
    "wrapping": "packaging",
    # Claims
    "health claim": "claims",
    "nutrition claim": "claims",
    # Labelling
    "compound ingredient": "labelling",
    "primary ingredient": "labelling",
    "allergen": "labelling",
    "gluten": "labelling",
    "wheat": "labelling",
    "nutrient": "labelling",
    "nutrition declaration": "labelling",
    "origin labelling": "labelling",
    "legal name": "labelling",
    "customary name": "labelling",
    "descriptive name": "labelling",
    "mandatory food information": "labelling",
    "field of vision": "labelling",
    "principal field of vision": "labelling",
    "legibility": "labelling",
    "means of distance communication": "labelling",
    "place of provenance": "labelling",
    "food information": "labelling",
    "food information law": "labelling",
    "mass caterer": "labelling",
    "trimmings": "labelling",
    "label": "labelling",
    # Safety
    "contaminant": "safety",
    "pesticide residues": "safety",
    "maximum residue level": "safety",
    "acceptable daily intake": "safety",
    "acute reference dose": "safety",
    "benchmark levels": "safety",
    "limit of determination": "safety",
    "good agricultural practice": "safety",
    "contamination": "safety",
    "food hygiene": "safety",
    "clean water": "safety",
    "potable water": "safety",
    "clean seawater": "safety",
    "radiological emergency": "safety",
    "incidental contamination": "safety",
    # Production/farming (from organic)
    "aquaculture": "production",
    "aquaculture products": "production",
    "plant production": "production",
    "plant products": "production",
    "plants": "production",
    "livestock production": "production",
    "primary production": "production",
    "primary products": "production",
    "farmer": "production",
    "holding": "production",
    "hatchery": "production",
    "nursery": "production",
    "laying hens": "production",
    "poultry house": "production",
    "pullets": "production",
    "mother plant": "production",
    "plant reproductive material": "production",
    "locally grown species": "production",
    "generation": "production",
    "conversion": "production",
    "soil-related crop cultivation": "production",
    "production cycle": "production",
    "production unit": "production",
    "organic production unit": "production",
    "non-organic production unit": "production",
    "organic production": "production",
    "agricultural area": "production",
    "agricultural raw material": "production",
    "usable area": "production",
    "veranda": "production",
    "energy from renewable sources": "production",
    "ionising radiation": "production",
    "veterinary treatment": "production",
    "water pollution": "production",
    "polyculture": "production",
    "pest": "production",
    "young child": "product_types",
    "infant": "product_types",
    # Official controls — curated product-relevant terms
    "animal by-products": "ingredients",
    "bivalve molluscs": "commodity_keywords",
    "composite product": "product_properties",
    "fishery products": "commodity_keywords",
    "fresh meat": "commodity_keywords",
    "gelatin": "ingredients",
    "live animals": "commodity_keywords",
    "meat preparations": "commodity_keywords",
    "mechanically separated meat": "commodity_keywords",
    "minced meat": "commodity_keywords",
    "milk": "commodity_keywords",
    "raw milk": "commodity_keywords",
    "rendered fats": "ingredients",
    "wild game": "commodity_keywords",
    "poultry meat": "commodity_keywords",
    "collagen": "ingredients",
    "colostrum": "commodity_keywords",
}

# UI group display names and descriptions
UI_GROUP_META = {
    "product_types": {
        "label": "Product type",
        "description": "What kind of food product is this?",
    },
    "ingredients": {
        "label": "Ingredients & additives",
        "description": "What ingredients or additive types does the product contain?",
    },
    "product_properties": {
        "label": "Product properties",
        "description": "Special characteristics of the product.",
    },
    "claims": {
        "label": "Marketing claims",
        "description": "Claims made on the label or in advertising.",
    },
    "packaging": {
        "label": "Packaging",
        "description": "Packaging material and type.",
    },
    "labelling": {
        "label": "Labelling concerns",
        "description": "Specific labelling requirements to check.",
    },
    "safety": {
        "label": "Safety & contaminants",
        "description": "Contaminant, hygiene, and safety concerns.",
    },
    "commodity_keywords": {
        "label": "Commodity type",
        "description": "Specific food commodity (triggers product-standard regulations).",
    },
    "production": {
        "label": "Production & farming",
        "description": "Production methods and agricultural context.",
    },
    "general": {
        "label": "General",
        "description": "General food law concepts.",
    },
    "other": {
        "label": "Other",
        "description": "Additional regulatory areas.",
    },
}


def classify_term(term: str, category: str) -> str | None:
    """Classify a term into a UI group. Returns None if excluded."""
    term_lower = term.lower().strip()

    if term_lower in EXCLUDE_TERMS:
        return None

    if len(term_lower) < 4 or len(term_lower) > 60:
        return None

    # Official controls: exclude all except curated allow-list
    if category == "official_controls" and term_lower not in _OC_ALLOW:
        return None

    if term_lower in FORCE_GROUP:
        return FORCE_GROUP[term_lower]

    return CATEGORY_TO_UI_GROUP.get(category)


def extract_options() -> dict:
    """Extract and classify all UI options."""
    entity_index = load_entity_index()

    # Collect unique terms with their classifications
    options: dict[str, list[dict]] = {}
    seen_terms: set[str] = set()

    # 1. Add defined terms from entity index
    for dt in entity_index.defined_terms:
        term_lower = dt.term_lower
        if term_lower in seen_terms:
            continue

        group = classify_term(term_lower, dt.category)
        if group is None:
            continue

        seen_terms.add(term_lower)
        options.setdefault(group, []).append({
            "term": dt.term,
            "source": "defined_term",
            "category": dt.category,
            "definition": dt.definition_snippet[:100] if dt.definition_snippet else "",
        })

    # 2. Add CATEGORY_ROUTING keys not already covered by defined terms
    for routing_key, categories in CATEGORY_ROUTING.items():
        if routing_key.lower() in seen_terms:
            continue

        # Determine UI group from the first mapped category
        cat = categories[0] if categories else ""
        group = classify_term(routing_key, cat)
        if group is None:
            # Routing keys should always be included — use category mapping
            group = CATEGORY_TO_UI_GROUP.get(cat, "other")

        seen_terms.add(routing_key.lower())
        options.setdefault(group, []).append({
            "term": routing_key,
            "source": "routing_key",
            "category": cat,
            "definition": "",
        })

    # Sort each group alphabetically
    for group in options:
        options[group] = sorted(options[group], key=lambda x: x["term"].lower())

    # Build output
    output = {
        "groups": {},
        "corpus_stats": {
            "regulations": len(CORPUS),
            "categories": len(CATEGORIES),
        },
    }

    for group_key, group_options in sorted(options.items()):
        meta = UI_GROUP_META.get(group_key, {"label": group_key, "description": ""})
        output["groups"][group_key] = {
            "label": meta["label"],
            "description": meta["description"],
            "options": [opt["term"] for opt in group_options],
            "details": group_options,
        }

    return output


def main() -> None:
    output = extract_options()

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {OUTPUT_PATH}")
    print(f"\nUI option groups:")
    for group_key, group_data in output["groups"].items():
        n = len(group_data["options"])
        print(f"  {group_data['label']:30s} ({n:3d} options): {group_data['options'][:5]}{'...' if n > 5 else ''}")

    total = sum(len(g["options"]) for g in output["groups"].values())
    print(f"\nTotal: {total} options across {len(output['groups'])} groups")


if __name__ == "__main__":
    main()
