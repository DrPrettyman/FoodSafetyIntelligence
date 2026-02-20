"""
EU Food Safety regulatory corpus definition.

Each entry maps a CELEX number to its regulatory category and short description.
This is the authoritative list of documents the system indexes.
"""

CORPUS: dict[str, dict] = {
    # --- General food law ---
    "32002R0178": {
        "category": "general_food_law",
        "title": "General Food Law Regulation",
        "description": "Lays down general principles and requirements of food law, "
        "establishes EFSA, procedures for food safety",
    },
    "32019R1381": {
        "category": "general_food_law",
        "title": "Transparency and sustainability of EU risk assessment in food chain",
        "description": "Amends several food chain regulations regarding transparency of EFSA",
    },
    "32004R0852": {
        "category": "general_food_law",
        "title": "Hygiene of foodstuffs",
        "description": "General hygiene rules for food business operators",
    },
    "32004R0853": {
        "category": "general_food_law",
        "title": "Hygiene rules for food of animal origin",
        "description": "Specific hygiene rules for products of animal origin",
    },
    "32011R0016": {
        "category": "general_food_law",
        "title": "Implementing measures for the Rapid Alert System for Food and Feed",
        "description": "RASFF notification procedures",
    },
    # --- Novel foods ---
    "32015R2283": {
        "category": "novel_food",
        "title": "Novel Foods Regulation",
        "description": "Rules on novel foods, including authorisation procedure and Union List",
    },
    "32017R2468": {
        "category": "novel_food",
        "title": "Novel food application requirements",
        "description": "Administrative and scientific requirements for novel food applications",
    },
    "32017R2469": {
        "category": "novel_food",
        "title": "Novel food application requirements (traditional foods from third countries)",
        "description": "Requirements for notifications of traditional foods from third countries",
    },
    "32017R2470": {
        "category": "novel_food",
        "title": "Union List of novel foods",
        "description": "Establishes the Union List of authorised novel foods",
    },
    "32018R0456": {
        "category": "novel_food",
        "title": "Procedural steps of the consultation process for novel food status",
        "description": "Procedure for determining novel food status",
    },
    # --- Food additives ---
    "32008R1333": {
        "category": "food_additives",
        "title": "Food Additives Regulation",
        "description": "Rules on food additives including Union Lists in Annexes II and III",
    },
    "32008R1331": {
        "category": "food_additives",
        "title": "Common authorisation procedure for food additives, enzymes, flavourings",
        "description": "Establishes the common authorisation procedure",
    },
    "32012R0231": {
        "category": "food_additives",
        "title": "Specifications for food additives",
        "description": "Purity criteria and specifications for food additives in Annexes",
    },
    # --- Food enzymes ---
    "32008R1332": {
        "category": "food_enzymes",
        "title": "Food Enzymes Regulation",
        "description": "Rules on food enzymes, including authorisation and labelling",
    },
    # --- Flavourings ---
    "32008R1334": {
        "category": "flavourings",
        "title": "Flavourings Regulation",
        "description": "Rules on flavourings and food ingredients with flavouring properties",
    },
    # --- Food contact materials ---
    "32004R1935": {
        "category": "food_contact_materials",
        "title": "Food Contact Materials framework regulation",
        "description": "General requirements for materials intended to come into contact with food",
    },
    "32011R0010": {
        "category": "food_contact_materials",
        "title": "Plastic food contact materials",
        "description": "Specific rules for plastic materials and articles intended to come "
        "into contact with food",
    },
    "32022R1616": {
        "category": "food_contact_materials",
        "title": "Recycled plastic food contact materials",
        "description": "Rules on recycled plastic materials intended to come into contact with food",
    },
    "32006R2023": {
        "category": "food_contact_materials",
        "title": "Good Manufacturing Practice for food contact materials",
        "description": "GMP requirements for food contact materials and articles",
    },
    # --- Labelling (Food Information to Consumers) ---
    "32011R1169": {
        "category": "labelling_fic",
        "title": "Food Information to Consumers (FIC) Regulation",
        "description": "Rules on food labelling, including allergens, nutrition declaration, "
        "origin labelling",
    },
    "32013R1337": {
        "category": "labelling_fic",
        "title": "Origin labelling for meat",
        "description": "Specific origin labelling rules for fresh, chilled, and frozen meat",
    },
    # --- Nutrition and health claims ---
    "32006R1924": {
        "category": "nutrition_health_claims",
        "title": "Nutrition and Health Claims Regulation",
        "description": "Rules on nutrition and health claims made on foods",
    },
    "32012R0432": {
        "category": "nutrition_health_claims",
        "title": "List of permitted health claims",
        "description": "Union list of permitted health claims made on foods (Article 13.1 claims)",
    },
    # --- Contaminants ---
    "32023R0915": {
        "category": "contaminants",
        "title": "Maximum levels for contaminants in food",
        "description": "Sets maximum permitted levels for contaminants including heavy metals, "
        "mycotoxins, PAHs, dioxins",
    },
    "32006R1881": {
        "category": "contaminants",
        "title": "Maximum levels for contaminants in food (predecessor)",
        "description": "Previous contaminants regulation, largely replaced by 2023/915 "
        "but some provisions may still apply",
    },
    # --- Official controls ---
    "32017R0625": {
        "category": "official_controls",
        "title": "Official Controls Regulation",
        "description": "Rules on official controls along the food chain including import controls",
    },
    # --- Organic production ---
    "32018R0848": {
        "category": "organic",
        "title": "Organic Production Regulation",
        "description": "Rules on organic production and labelling of organic products",
    },
    # --- Food for specific groups ---
    "32013R0609": {
        "category": "food_specific_groups",
        "title": "Food for Specific Groups Regulation",
        "description": "Rules on food for infants, young children, food for special medical "
        "purposes, total diet replacement for weight control",
    },
    "32016R0127": {
        "category": "food_specific_groups",
        "title": "Requirements for infant formula and follow-on formula",
        "description": "Compositional and labelling requirements for infant and follow-on formula",
    },
    # --- Food supplements ---
    "32002L0046": {
        "category": "food_supplements",
        "title": "Food Supplements Directive",
        "description": "Rules on food supplements including permitted vitamins, minerals, "
        "and their forms",
    },
    # --- GMOs ---
    "32003R1829": {
        "category": "gmo",
        "title": "GM Food and Feed Regulation",
        "description": "Rules on genetically modified food and feed, authorisation and labelling",
    },
    "32003R1830": {
        "category": "gmo",
        "title": "Traceability and labelling of GMOs",
        "description": "Traceability of GMO products and labelling requirements",
    },
    # --- Vitamins and minerals in foods ---
    "32006R1925": {
        "category": "fortification",
        "title": "Addition of vitamins and minerals to foods",
        "description": "Rules on fortification — adding vitamins and minerals to foods",
    },
}

CATEGORIES = {
    "general_food_law": "General food law and hygiene",
    "novel_food": "Novel foods",
    "food_additives": "Food additives",
    "food_enzymes": "Food enzymes",
    "flavourings": "Flavourings",
    "food_contact_materials": "Food contact materials",
    "labelling_fic": "Food Information to Consumers (labelling)",
    "nutrition_health_claims": "Nutrition and health claims",
    "contaminants": "Contaminants",
    "official_controls": "Official controls",
    "organic": "Organic production",
    "food_specific_groups": "Food for specific groups (infants, medical purposes)",
    "food_supplements": "Food supplements",
    "gmo": "Genetically modified food and feed",
    "fortification": "Fortification (vitamins and minerals added to foods)",
}
