"""
Discover EU food safety regulations via the EUR-Lex SPARQL endpoint.

Uses EU directory codes to find legislation classified under foodstuffs
and food safety, then filters out noise (individual product decisions,
repealing acts, etc.), finds latest consolidated versions, and classifies
regulations into corpus categories.

Run with: python -m src.ingestion.eurlex_discovery
Outputs: data/discovery/discovery_report.json
"""

import json
import logging
import re
import urllib.parse
import urllib.request
from pathlib import Path

logger = logging.getLogger(__name__)

SPARQL_ENDPOINT = "https://publications.europa.eu/webapi/rdf/sparql"
SPARQL_TIMEOUT = 90  # seconds

# EU Directory of Legal Acts codes relevant to food safety.
# 133014 = "Foodstuffs" — the core food law classification
# 152030 = "Protection of health" — food safety under public health
DIRECTORY_CODES = {
    "133014": "Foodstuffs",
    "152030": "Protection of health",
}

# Title substrings that indicate noise — individual operational acts, not framework regulations.
# These are "strong" excludes that always apply, even if a category rule matches.
EXCLUDE_TITLE_PATTERNS = [
    # --- Corrections ---
    "correcting",
    "corrigendum",
    "adapting to technical progress",
    "adapting certain directives in the field of food safety",
    "derogation",
    "derogating from directive",
    "replacing annex",
    "annexes to regulation",
    "supplementing the annex",
    "supplementing annex",
    "adapting annex",
    # --- Individual product authorisations / refusals ---
    "placing on the market",
    "authorising the placing",
    "authorizing the placing",
    "granting a union authorisation for the biocidal",
    "granting a union authorisation for the single biocidal",
    "concerning the authorisation of",
    "concerning the provisional authorisation",
    "concerning the permanent authorisation",
    "concerning the provisional authorization",
    "refusing to authorise",
    "non-approval of",
    "non-inclusion of",
    "on the authorisation and refusal of authorisation",
    "authorisation of a health claim",
    "authorising a health claim",
    "concerning the extension of uses",
    "concerning the suspension of",
    "authorising an extension of use",
    "authorising the extension of use",
    "authorising the change of the",
    "authorising a change of the",
    "authorising changes in the",
    "authorising the change of specifications",
    "approving the pre-export checks",
    "approving active chlorine",
    "approving ozone",
    "approving didecyldimethyl",
    "approving formic acid",
    "approving reaction mass",
    "approving trihydrogen",
    # --- Emergency / temporary / transitional measures ---
    "emergency measures",
    "protective measures",
    "transitional measures",
    "transitional arrangements",
    "temporary measures to contain risks",
    # --- Non-food sectors ---
    "safety of toys",
    "eco-label",
    "ecolabel",
    "energy efficiency labelling",
    "energy-efficiency labelling",
    "advertising of medicinal",
    "dangerous preparation",
    "restrictions on the marketing and use",
    "general product safety",
    "quality and safety of human organ",
    "pyrotechnic",
    "explosives for civil",
    "system for the identification and traceability of explosives",
    "drug precursor",
    "monitoring of trade between the community and third countries in drug",
    "animal health conditions governing the movement",
    "in vitro diagnostic",
    "reference laboratory for equine",
    "reference laboratory for bee health",
    "compulsory licensing for crisis",
    "veterinary entry document",
    "animal health certificates",
    "official certificates and private attestations",
    "model certificate for products of animal origin",
    "implementing measures for certain products of animal origin",
    "substances having a hormonal",
    "prohibiting the use in livestock",
    "protection of workers from the risks",
    "tobacco",
    "cosmetic",
    "biocidal product",
    "pesticides residues",
    "pharmacologically active",
    "regulation (eu) 2023/988",  # General Product Safety Regulation
    "regulation (eu) 2017/745",  # Medical Devices Regulation
    "supplementing directive (eu) 2020/2184",  # Drinking water directive
    "codes and corresponding types of devices",
    "common specifications for certain class",
    "common specifications for the groups of products",
    # --- Chernobyl / nuclear accident agricultural imports ---
    "imports of agricultural products originating in third countries",
    "products excluded from the application of council regulation",
    "extending regulation (eec) no 1707",
    "extending regulation (eec) no 737",
    "following the accident at the chernobyl",
    # --- Animal health / veterinary (not food safety) ---
    "foot-and-mouth disease",
    "classical swine fever",
    "bovine spongiform encephalopathy",
    "african swine fever",
    "animal health rules governing",
    "avian influenza",
    "the beef market",
    "control of salmonella",
    # --- Administrative / budget / institutional ---
    "financial contribution",
    "financing of",
    "appointing",
    "position to be adopted",
    "position to be taken",
    "national provisions notified",
    "consumer policy strategy",
    "state aid",
    "statement of revenue",
    "advisory group",
    "members of the",
    "allocating to the member states resources",
    "resources to be charged",
    "plan allocating",
    "cross-border credit transfer",
    "revoking the designation",
    "promotional and publicity measures",
    # --- Operational / data / statistical ---
    "output indicators relevant for",
    "statistical data to be submitted",
    "standard data formats for the submission",
    "making certain information available to the public",
    "maximum residue limit to be considered for action",
    "facility for rapid response",
    "checks for conformity with the rules on product safety",
    "conformity to the marketing standards applicable to fruit",
    # --- Surveillance / monitoring programmes ---
    "concerning a coordinated multiannual control programme",
    "multiannual national control programme",
    "survey on the prevalence",
    "regarding the form and content of the applications",
    "working programme",
    "reference laboratories",
    "molecular analytical data",
    # --- Imports (non-food or superseded) ---
    "the import of",
    "suspending imports",
    "prohibiting the placing",
    "import of polyamide",
    # --- Specific product regulations (not food) ---
    "fodder grain",
    "spirit drink",
    "aromatised wine",
    "aromatized wine",
    "tar yield of cigarettes",
    "cigarettes",
    "geographical indication",
    "designations of origin",
    "the registration of",
    "registration of the name",
    # --- Miscellaneous operational ---
    "nectars without the addition of sugars",
    "evaluation programme for flavouring",
    "evaluation programme in application",
    "plasticisers in gaskets",
    "marketing of olive oil",
    "assistance to the commission and cooperation by the member states",
    "scientific examination of questions relating to food",
    "adopting a list of materials whose circulation",
    "maximum residue limit to be considered for control",
    "approving operations to check conformity",
]

# "Weak" exclude patterns: only applied when no category rule matches.
# Framework regulations like "on novel foods, amending Regulation (EC) No 258/97"
# contain "amending" but ARE substantive legislation — the category rule for "novel food"
# will match and override the weak exclude.  Amendment-only acts like
# "amending Annex I to Regulation (EC) No 1334/2008" won't match any category rule
# and will be excluded.
WEAK_EXCLUDE_PATTERNS = [
    "amending",
    "repealing directive",
    "repealing regulation",
    "repealing council",
    "repealing commission",
]

# Category assignment rules: (priority order) patterns match against title (lowercase).
# More specific rules should come before broader ones to avoid misclassification.
CATEGORY_RULES = [
    # Specific groups / infant formula
    ("infant formula", "food_specific_groups"),
    ("follow-on formula", "food_specific_groups"),
    ("food for specific groups", "food_specific_groups"),
    ("food for special medical purposes", "food_specific_groups"),
    ("total diet replacement", "food_specific_groups"),
    ("young child", "food_specific_groups"),
    ("processed cereal", "food_specific_groups"),
    ("baby food", "food_specific_groups"),
    ("specific nutritional purposes", "food_specific_groups"),
    ("food intended for infants", "food_specific_groups"),
    ("particular nutritional uses", "food_specific_groups"),
    ("weight reduction", "food_specific_groups"),
    ("dietary food", "food_specific_groups"),
    # Novel foods
    ("novel food", "novel_food"),
    ("traditional food", "novel_food"),
    # Food supplements
    ("food supplement", "food_supplements"),
    # Food additives (including old directives on sweeteners, colours, etc.)
    ("food additive", "food_additives"),
    ("common authorisation procedure", "food_additives"),
    ("specifications for food additives", "food_additives"),
    ("re-evaluation of approved food additive", "food_additives"),
    ("sweeteners for use in foodstuffs", "food_additives"),
    ("colours for use in foodstuffs", "food_additives"),
    ("antioxidants which may be used in foodstuffs", "food_additives"),
    ("antioxidants authorised for use in foodstuffs", "food_additives"),
    ("antioxidants authorized for use in foodstuffs", "food_additives"),
    ("emulsifiers, stabilizers, thickeners", "food_additives"),
    ("emulsifiers, stabilisers, thickeners", "food_additives"),
    ("criteria of purity for emulsifiers", "food_additives"),
    ("criteria of purity for antioxidants", "food_additives"),
    ("purity criteria concerning sweeteners", "food_additives"),
    ("purity criteria concerning colours", "food_additives"),
    # Flavourings
    ("flavouring", "flavourings"),
    ("smoke flavouring", "flavourings"),
    ("implementing regulation (ec) no 2065/2003", "flavourings"),
    # Food enzymes
    ("food enzyme", "food_enzymes"),
    # Food contact materials
    ("food contact material", "food_contact_materials"),
    ("plastic material", "food_contact_materials"),
    ("recycled plastic", "food_contact_materials"),
    ("good manufacturing practice", "food_contact_materials"),
    ("materials and articles intended to come into contact", "food_contact_materials"),
    ("materials and articles made of regenerated cellulose", "food_contact_materials"),
    ("ceramic article", "food_contact_materials"),
    ("epoxy derivative", "food_contact_materials"),
    ("vinyl chloride", "food_contact_materials"),
    ("testing migration", "food_contact_materials"),
    ("active and intelligent material", "food_contact_materials"),
    ("symbol that may accompany materials", "food_contact_materials"),
    ("n-nitrosamine", "food_contact_materials"),
    # Labelling / FIC
    ("food information to consumers", "labelling_fic"),
    ("nutrition labelling", "labelling_fic"),
    ("labelling of foodstuffs", "labelling_fic"),
    ("labelling of certain foodstuffs", "labelling_fic"),
    ("identifying the lot", "labelling_fic"),
    ("indications or marks identifying", "labelling_fic"),
    ("compulsory indication on the labelling", "labelling_fic"),
    ("absence or reduced presence", "labelling_fic"),
    ("provision of information to consumers", "labelling_fic"),
    ("labelling requirements for sprouts", "labelling_fic"),
    # Nutrition and health claims
    ("nutrition and health claim", "nutrition_health_claims"),
    ("health claim", "nutrition_health_claims"),
    ("nutrition claim", "nutrition_health_claims"),
    ("generic descriptor", "nutrition_health_claims"),
    ("list of permitted health claims", "nutrition_health_claims"),
    # Contaminants (including radioactive contamination)
    ("contaminant", "contaminants"),
    ("maximum level", "contaminants"),
    ("acrylamide", "contaminants"),
    ("microbiological criteria", "contaminants"),
    ("erucic acid", "contaminants"),
    ("nitrate", "contaminants"),
    ("maximum residue levels of pesticides", "contaminants"),
    ("maximum residue levels for acephate", "contaminants"),
    ("radioactive contamination of foodstuffs", "contaminants"),
    ("radioactive contamination in minor", "contaminants"),
    ("permitted levels of radioactive contamination", "contaminants"),
    ("exporting foodstuffs and feedingstuffs following a nuclear", "contaminants"),
    # Official controls (including 2017/625 implementing chain)
    ("official control", "official_controls"),
    ("traceability requirement", "official_controls"),
    ("import control", "official_controls"),
    ("border control", "official_controls"),
    ("methods of sampling and analysis", "official_controls"),
    ("methods of sampling and performance", "official_controls"),
    ("methods of sampling for chemical analysis", "official_controls"),
    ("sampling methods and the methods of analysis", "official_controls"),
    ("analytical methods applicable to official controls", "official_controls"),
    ("methods of analysis for verifying", "official_controls"),
    ("methods of analysis for testing", "official_controls"),
    ("methods of analysis for the official control", "official_controls"),
    ("methods of analysis for edible caseins", "official_controls"),
    ("rapid alert system", "official_controls"),
    ("information management system", "official_controls"),
    ("procedures at border control", "official_controls"),
    ("approval of establishments", "official_controls"),
    ("certification requirements for imports", "official_controls"),
    ("traceability requirements for sprouts", "official_controls"),
    ("lists of third countries", "official_controls"),
    ("monitoring of temperatures", "official_controls"),
    ("temperature", "official_controls"),
    ("supplementing regulation (eu) 2017/625", "official_controls"),
    ("application of regulation (eu) 2017/625", "official_controls"),
    ("prior notification of consignments", "official_controls"),
    ("imports of food and feed originating", "official_controls"),
    ("special guarantees concerning salmonella", "official_controls"),
    ("reduction of salmonella", "official_controls"),
    ("prevalence of certain salmonella", "official_controls"),
    ("microbiological contamination", "official_controls"),
    ("conditions for the entry into the union", "official_controls"),
    ("imports of guar gum", "official_controls"),
    ("veterinary certification conditions", "official_controls"),
    ("frequency rates", "official_controls"),
    ("model official certificate", "official_controls"),
    # Organic
    ("organic production", "organic"),
    ("organic product", "organic"),
    # GMO
    ("genetically modified", "gmo"),
    ("traceability and labelling of gmo", "gmo"),
    ("unique identifier", "gmo"),
    # Fortification
    ("addition of vitamins", "fortification"),
    ("addition of mineral", "fortification"),
    # Feed
    ("feed hygiene", "feed"),
    ("animal feedingstuff", "feed"),
    # Food irradiation
    ("irradiation", "food_irradiation"),
    ("ionising radiation", "food_irradiation"),
    # General food law / hygiene (broad, check last)
    ("general food law", "general_food_law"),
    ("general principles and requirements of food law", "general_food_law"),
    ("hygiene of foodstuffs", "general_food_law"),
    ("hygiene rules", "general_food_law"),
    ("transparency and sustainability", "general_food_law"),
    ("risk assessment in food chain", "general_food_law"),
    ("food law", "general_food_law"),
    ("food hygiene", "general_food_law"),
    ("food business operator", "general_food_law"),
    ("sprout", "general_food_law"),
    ("food chain", "general_food_law"),
    ("microbiological surface contamination", "general_food_law"),
    ("the procedure applied by the european food safety authority", "general_food_law"),
    ("regulation (ec) no 178/2002", "general_food_law"),
    # Product standards (compositional)
    ("relating to honey", "product_standards"),
    ("relating to cocoa", "product_standards"),
    ("relating to sugars", "product_standards"),
    ("relating to fruit juice", "product_standards"),
    ("relating to fruit jam", "product_standards"),
    ("relating to coffee extract", "product_standards"),
    ("relating to certain partly or wholly dehydrated", "product_standards"),
    ("relating to certain lactoproteins", "product_standards"),
    ("relating to caseins", "product_standards"),
    ("natural mineral water", "product_standards"),
    ("extraction solvent", "product_standards"),
    ("quick-frozen foodstuff", "product_standards"),
    ("composition and labelling of foodstuffs suitable", "product_standards"),
    ("fruit juices and certain similar products", "product_standards"),
    ("sugars intended for human consumption", "product_standards"),
]

# Core food safety regulations classified under non-food directory codes.
# These are manually included because their directory codes (e.g., 035030
# "Animal products", 035010 "Veterinary legislation") are too broad to search.
MANUAL_INCLUDE_CELEX = {
    "32004R0853": "general_food_law",    # Hygiene for food of animal origin (dir: 035030)
    "32011R0016": "official_controls",   # RASFF implementing measures (dir: 035010)
    "32013R1337": "labelling_fic",       # Origin labelling for meat (dir: 152020)
    "32018R0848": "organic",             # Organic Production Regulation (dir: 152040)
}

DISCOVERY_DIR = Path("data/discovery")


def query_sparql(sparql_query: str, retries: int = 3) -> list[dict]:
    """Execute a SPARQL query against the EUR-Lex endpoint.

    Returns a list of result bindings (dicts with variable names as keys).
    Retries on transient errors (timeouts, 502/503).
    """
    import time

    params = urllib.parse.urlencode({
        "query": sparql_query,
        "format": "application/json",
    })
    url = f"{SPARQL_ENDPOINT}?{params}"

    for attempt in range(retries):
        req = urllib.request.Request(url)
        try:
            with urllib.request.urlopen(req, timeout=SPARQL_TIMEOUT) as resp:
                data = json.loads(resp.read())
            bindings = data.get("results", {}).get("bindings", [])
            return [{k: v["value"] for k, v in b.items()} for b in bindings]
        except urllib.error.HTTPError as e:
            if e.code in (502, 503) and attempt < retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning(f"SPARQL HTTP {e.code}, retrying in {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"SPARQL HTTP {e.code}: {e.reason}")
            return []
        except (urllib.error.URLError, TimeoutError, OSError) as e:
            if attempt < retries - 1:
                wait = 5 * (attempt + 1)
                logger.warning(f"SPARQL timeout/error, retrying in {wait}s...")
                time.sleep(wait)
                continue
            logger.error(f"SPARQL error: {e}")
            return []

    return []


def discover_food_regulations() -> list[dict]:
    """Query EUR-Lex for food-related regulations and directives.

    Uses EU directory codes for targeted search. Returns a list of dicts
    with keys: celex, title, directory_codes.
    """
    dir_code_uris = " ".join(
        f"<http://publications.europa.eu/resource/authority/dir-eu-legal-act/{code}>"
        for code in DIRECTORY_CODES
    )

    sparql = f"""
    PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

    SELECT DISTINCT ?celex ?title ?dir WHERE {{
        ?work cdm:resource_legal_id_celex ?celex .
        ?work cdm:resource_legal_is_about_concept_directory-code ?dir .

        ?expr cdm:expression_belongs_to_work ?work .
        ?expr cdm:expression_uses_language
            <http://publications.europa.eu/resource/authority/language/ENG> .
        ?expr cdm:expression_title ?title .

        VALUES ?dir {{ {dir_code_uris} }}

        FILTER(STRSTARTS(?celex, '3'))
    }}
    ORDER BY ?celex
    """
    logger.info("Querying EUR-Lex SPARQL for food regulations...")
    results = query_sparql(sparql)
    logger.info(f"SPARQL returned {len(results)} rows")

    # Group by CELEX, collecting directory codes
    seen: dict[str, dict] = {}
    for r in results:
        celex = r["celex"]
        dir_code = r["dir"].rsplit("/", 1)[-1]
        if celex not in seen:
            seen[celex] = {
                "celex": celex,
                "title": r["title"],
                "directory_codes": [],
            }
        if dir_code not in seen[celex]["directory_codes"]:
            seen[celex]["directory_codes"].append(dir_code)

    logger.info(f"Deduplicated to {len(seen)} unique regulations")
    return list(seen.values())


def _normalize(text: str) -> str:
    """Normalize whitespace (including non-breaking spaces from EUR-Lex)."""
    return re.sub(r"\s+", " ", text).strip()


def filter_candidates(candidates: list[dict]) -> list[dict]:
    """Filter out noise: individual decisions, amendments, etc.

    Uses a two-tier exclusion strategy:
    - Strong excludes (EXCLUDE_TITLE_PATTERNS): always filter, no exceptions.
    - Weak excludes (WEAK_EXCLUDE_PATTERNS): only filter if the regulation
      doesn't match any category rule.  This handles framework regulations
      whose titles contain "amending" or "repealing" (e.g., "on novel foods,
      amending Regulation (EC) No 258/97") — the category rule for
      "novel food" takes precedence.
    """
    kept = []
    for reg in candidates:
        celex = reg["celex"]
        title = reg.get("title", "")
        title_lower = _normalize(title.lower())

        # Skip corrigenda (CELEX contains R(01) etc.)
        if re.search(r"R\(\d+\)", celex):
            continue

        # Only keep Regulations (R) and Directives (L)
        if len(celex) > 5:
            doc_type = celex[5]
            if doc_type not in ("R", "L"):
                continue

        # Strong excludes — always apply
        if any(pattern in title_lower for pattern in EXCLUDE_TITLE_PATTERNS):
            continue

        # Weak excludes — "amending" and "repealing" appear in both:
        #   1. Framework regulations: "on novel foods, amending Regulation (EC)..."
        #   2. Amendment-only acts:   "amending Annex I to Regulation (EC)..."
        # Framework regulations have substantive content BEFORE the amending/repealing
        # clause, signalled by a preceding comma or "and".  Amendment-only acts go
        # straight from the date to "amending" with no such marker.
        if any(pattern in title_lower for pattern in WEAK_EXCLUDE_PATTERNS):
            is_framework = (
                ", amending" in title_lower
                or "and amending" in title_lower
                or ", repealing" in title_lower
                or "and repealing" in title_lower
            )
            if not is_framework:
                continue

        kept.append(reg)

    logger.info(f"Filtered {len(candidates)} → {len(kept)} candidate regulations")
    return kept


def get_latest_consolidated(celex_ids: list[str]) -> dict[str, str | None]:
    """Find the latest consolidated CELEX ID for each base CELEX.

    Returns {base_celex: consolidated_celex_or_None}.
    """
    if not celex_ids:
        return {}

    # Convert base CELEX to consolidated prefix: 32002R0178 → 02002R0178
    prefixes = {}
    for cid in celex_ids:
        prefix = "0" + cid[1:]
        prefixes[cid] = prefix

    result = {cid: None for cid in celex_ids}

    for i in range(0, len(celex_ids), 30):
        batch = celex_ids[i : i + 30]
        values = " ".join(f"'{prefixes[c]}'" for c in batch)
        sparql = f"""
        PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>

        SELECT ?prefix (MAX(?celex) as ?latest) WHERE {{
            ?work cdm:resource_legal_id_celex ?celex .
            VALUES ?prefix {{ {values} }}
            FILTER(STRSTARTS(?celex, ?prefix))
        }} GROUP BY ?prefix
        """
        rows = query_sparql(sparql)

        for row in rows:
            prefix_val = row["prefix"]
            latest = row["latest"]
            for base_celex, base_prefix in prefixes.items():
                if base_prefix == prefix_val:
                    result[base_celex] = latest
                    break

    found = sum(1 for v in result.values() if v is not None)
    logger.info(
        f"Found consolidated versions for {found}/{len(celex_ids)} regulations"
    )
    return result


def classify_regulation(title: str) -> str:
    """Assign a corpus category based on the regulation title.

    Returns a category string matching CATEGORIES keys.
    Falls back to 'unclassified' if no rule matches.
    """
    title_lower = _normalize(title.lower())
    for pattern, category in CATEGORY_RULES:
        if pattern in title_lower:
            return category
    return "unclassified"


def run_discovery(output_dir: Path = DISCOVERY_DIR) -> dict:
    """Run the full discovery pipeline.

    1. Query SPARQL for food regulations (using directory codes)
    2. Filter out noise
    3. Find latest consolidated versions
    4. Classify into categories
    5. Save report

    Returns the discovery report dict.
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Step 1: Discover via SPARQL
    candidates = discover_food_regulations()

    # Step 2: Title/type filtering
    filtered = filter_candidates(candidates)

    # Step 2b: Add manually-included core regulations not found by directory codes
    found_celex = {r["celex"] for r in filtered}
    manual_to_add = {c: cat for c, cat in MANUAL_INCLUDE_CELEX.items() if c not in found_celex}
    if manual_to_add:
        # Fetch titles from SPARQL
        for celex, category in manual_to_add.items():
            sparql = f"""
            PREFIX cdm: <http://publications.europa.eu/ontology/cdm#>
            SELECT ?title WHERE {{
                ?work cdm:resource_legal_id_celex ?celex .
                ?expr cdm:expression_belongs_to_work ?work .
                ?expr cdm:expression_uses_language
                    <http://publications.europa.eu/resource/authority/language/ENG> .
                ?expr cdm:expression_title ?title .
                FILTER(STR(?celex) = '{celex}')
            }} LIMIT 1
            """
            rows = query_sparql(sparql)
            title = rows[0]["title"] if rows else f"(manual include — {category})"
            filtered.append({
                "celex": celex,
                "title": title,
                "directory_codes": [],
                "category": category,
            })
            logger.info(f"Manually added {celex} ({category})")

    # Step 3: Find consolidated versions
    celex_ids = [r["celex"] for r in filtered]
    consolidated = get_latest_consolidated(celex_ids)
    for reg in filtered:
        reg["consolidated_celex"] = consolidated.get(reg["celex"])

    # Step 4: Classify (skip if category already set from manual include)
    for reg in filtered:
        if "category" not in reg:
            reg["category"] = classify_regulation(reg["title"])

    # Step 5: Build report
    by_category: dict[str, int] = {}
    for reg in filtered:
        cat = reg["category"]
        by_category[cat] = by_category.get(cat, 0) + 1

    report = {
        "total_sparql_results": len(candidates),
        "after_filtering": len(filtered),
        "with_consolidated": sum(
            1 for r in filtered if r["consolidated_celex"] is not None
        ),
        "by_category": dict(sorted(by_category.items())),
        "regulations": filtered,
    }

    report_path = output_dir / "discovery_report.json"
    report_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info(f"Discovery report saved to {report_path}")
    logger.info(
        f"Summary: {report['after_filtering']} regulations, "
        f"{report['with_consolidated']} with consolidated text, "
        f"{len(by_category)} categories"
    )

    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
    report = run_discovery()

    print(f"\n{'=' * 70}")
    print(f"Discovery Report: {report['after_filtering']} regulations found")
    print(f"{'=' * 70}")
    print(f"  SPARQL results:   {report['total_sparql_results']}")
    print(f"  After filtering:  {report['after_filtering']}")
    print(f"  With consolidated: {report['with_consolidated']}")
    print(f"\nBy category:")
    for cat, count in sorted(report["by_category"].items()):
        print(f"  {cat:<30} {count:>3}")
    print(f"\nRegulations:")
    for reg in report["regulations"]:
        consol = reg["consolidated_celex"] or "(none)"
        print(f"  {reg['celex']:<15} [{reg['category']:<25}] {consol}")
        print(f"    {reg['title'][:100]}")
