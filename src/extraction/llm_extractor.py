"""
LLM-based structured extraction of compliance requirements from regulatory articles.

Uses an LLM to extract typed ComplianceRequirement objects from retrieved regulatory
text. The LLM is used here — and only here — because turning dense legal prose into
structured requirements genuinely requires language understanding.

Supports three providers:
- **anthropic**: Anthropic API with tool_use (function calling). Requires ANTHROPIC_API_KEY.
- **openai**: OpenAI API with function calling. Requires OPENAI_API_KEY.
- **claude-code**: Claude Code CLI (`claude -p`). No API key needed.
"""

import json
import os
import re
import shutil
import subprocess

import anthropic

from src.extraction.schemas import (
    ComplianceRequirement,
    ExtractionResult,
    Priority,
    RequirementType,
)

# Provider defaults
ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
OPENAI_MODEL = "gpt-4o"
MAX_TOKENS = 4096

SYSTEM_PROMPT = """\
You are a regulatory compliance analyst specialising in EU food safety law.

Your task: given regulatory article text and a product context, extract each
concrete compliance requirement as a structured object.

Rules:
- Extract ONLY requirements that are explicitly stated in the source text.
- Do NOT invent requirements not present in the text.
- Each requirement should be a specific, actionable obligation (not a definition or background).
- If an article defines terms but imposes no obligation, return zero requirements.
- Set confidence to 0.9+ only when the requirement is unambiguous and clearly stated.
- Set confidence to 0.5-0.8 when the requirement may not apply to all product types.
- Set confidence below 0.5 when the requirement's applicability is uncertain.
- For cross_references, extract CELEX-style regulation numbers (e.g. "32002R0178") when mentioned.
- Keep requirement_summary concise: 1-2 sentences, plain English, actionable."""

FEW_SHOT_EXAMPLE = {
    "article_text": """[32015R2283] CHAPTER II REQUIREMENTS FOR PLACING NOVEL FOODS ON THE MARKET WITHIN THE UNION Article 7 — General conditions for inclusion of novel foods in the Union list
The Commission shall only authorise and include a novel food in the Union list if it complies with the following conditions:
(a) the food does not, on the basis of the scientific evidence available, pose a safety risk to human health;
(b) the food's intended use does not mislead the consumer;
(c) where the food is intended to replace another food, it does not differ from that food in such a way that its normal consumption would be nutritionally disadvantageous for the consumer.""",
    "product_context": "Novel food insect protein bar",
    "expected_output": [
        {
            "regulation_id": "32015R2283",
            "article_number": 7,
            "article_title": "General conditions for inclusion of novel foods in the Union list",
            "requirement_summary": "A novel food may only be placed on the EU market if it has been authorised and included in the Union list. Authorisation requires demonstrating the food poses no safety risk, does not mislead consumers, and is not nutritionally disadvantageous compared to foods it replaces.",
            "requirement_type": "authorisation",
            "priority": "before_launch",
            "applicable_to": "food business operators placing novel foods on the EU market",
            "conditions": "",
            "cross_references": [],
            "source_text_snippet": "The Commission shall only authorise and include a novel food in the Union list if it complies with the following conditions",
            "confidence": 0.95,
        }
    ],
}

# Tool/function definition matching the ComplianceRequirement schema
_REQUIREMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "regulation_id": {
            "type": "string",
            "description": "CELEX number, e.g. '32015R2283'",
        },
        "article_number": {
            "type": "integer",
            "description": "Article number",
        },
        "article_title": {
            "type": "string",
            "description": "Title of the article",
        },
        "requirement_summary": {
            "type": "string",
            "description": "Plain-English summary (1-2 sentences)",
        },
        "requirement_type": {
            "type": "string",
            "enum": [e.value for e in RequirementType],
        },
        "priority": {
            "type": "string",
            "enum": [e.value for e in Priority],
        },
        "applicable_to": {
            "type": "string",
            "description": "Who this applies to",
        },
        "conditions": {
            "type": "string",
            "description": "Conditions for applicability (empty if universal)",
        },
        "cross_references": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Referenced CELEX numbers",
        },
        "source_text_snippet": {
            "type": "string",
            "description": "Key supporting phrase from source text",
        },
        "confidence": {
            "type": "number",
            "description": "Confidence 0-1",
        },
    },
    "required": [
        "regulation_id",
        "article_number",
        "article_title",
        "requirement_summary",
        "requirement_type",
        "priority",
        "confidence",
    ],
}

# Anthropic tool_use format
EXTRACTION_TOOL = {
    "name": "submit_requirements",
    "description": "Submit the extracted compliance requirements from the regulatory text.",
    "input_schema": {
        "type": "object",
        "properties": {
            "requirements": {
                "type": "array",
                "description": "List of compliance requirements extracted from the articles. Empty if no actionable requirements found.",
                "items": _REQUIREMENT_SCHEMA,
            },
        },
        "required": ["requirements"],
    },
}

# OpenAI function calling format
_OPENAI_FUNCTION = {
    "type": "function",
    "function": {
        "name": "submit_requirements",
        "description": "Submit the extracted compliance requirements from the regulatory text.",
        "parameters": {
            "type": "object",
            "properties": {
                "requirements": {
                    "type": "array",
                    "description": "List of compliance requirements extracted from the articles.",
                    "items": _REQUIREMENT_SCHEMA,
                },
            },
            "required": ["requirements"],
        },
    },
}


def _build_user_message(articles: list[dict], product_context: str) -> str:
    """Build the user message with article texts and product context."""
    parts = [f"Product context: {product_context}\n"]

    parts.append("--- FEW-SHOT EXAMPLE ---")
    parts.append(f"Article text:\n{FEW_SHOT_EXAMPLE['article_text']}\n")
    parts.append(f"Product context: {FEW_SHOT_EXAMPLE['product_context']}\n")
    parts.append(
        "Expected extraction:\n"
        + json.dumps(FEW_SHOT_EXAMPLE["expected_output"], indent=2)
    )
    parts.append("--- END EXAMPLE ---\n")

    parts.append("Now extract requirements from the following articles:\n")

    for i, article in enumerate(articles, 1):
        parts.append(f"--- ARTICLE {i} ---")
        parts.append(article["text"])
        parts.append("")

    parts.append(
        "Extract all actionable compliance requirements from the articles above. "
        "Use the submit_requirements tool to return your extraction. "
        "If an article contains no actionable requirements (e.g. only definitions), skip it."
    )

    return "\n".join(parts)


def _parse_requirements(raw_reqs: list[dict]) -> list[ComplianceRequirement]:
    """Validate raw dicts through Pydantic, skipping malformed ones."""
    requirements = []
    for raw in raw_reqs:
        try:
            req = ComplianceRequirement(**raw)
            requirements.append(req)
        except Exception:
            continue
    return requirements


# --- Anthropic provider ---


def _extract_anthropic(
    user_message: str,
    api_key: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """Extract requirements using Anthropic API with tool_use."""
    key = api_key or os.environ.get("ANTHROPIC_API_KEY", "")
    if not key:
        raise ValueError(
            "No API key provided. Set ANTHROPIC_API_KEY environment variable or pass api_key."
        )

    client = anthropic.Anthropic(api_key=key)
    response = client.messages.create(
        model=model or ANTHROPIC_MODEL,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        tools=[EXTRACTION_TOOL],
        tool_choice={"type": "tool", "name": "submit_requirements"},
        messages=[{"role": "user", "content": user_message}],
    )

    for block in response.content:
        if block.type == "tool_use" and block.name == "submit_requirements":
            return block.input.get("requirements", [])
    return []


# --- OpenAI provider ---


def _extract_openai(
    user_message: str,
    api_key: str | None = None,
    model: str | None = None,
) -> list[dict]:
    """Extract requirements using OpenAI API with function calling."""
    try:
        import openai
    except ImportError:
        raise ImportError(
            "OpenAI provider requires the 'openai' package. "
            "Install it with: pip install openai"
        )

    key = api_key or os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise ValueError(
            "No API key provided. Set OPENAI_API_KEY environment variable or pass api_key."
        )

    client = openai.OpenAI(api_key=key)
    response = client.chat.completions.create(
        model=model or OPENAI_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_message},
        ],
        tools=[_OPENAI_FUNCTION],
        tool_choice={"type": "function", "function": {"name": "submit_requirements"}},
    )

    message = response.choices[0].message
    if message.tool_calls:
        for tool_call in message.tool_calls:
            if tool_call.function.name == "submit_requirements":
                args = json.loads(tool_call.function.arguments)
                return args.get("requirements", [])
    return []


# --- Claude Code CLI provider ---


def _extract_claude_code(
    user_message: str,
    model: str | None = None,
) -> list[dict]:
    """Extract requirements using Claude Code CLI (`claude -p`).

    No API key needed — uses whatever authentication Claude Code has configured.
    """
    claude_path = shutil.which("claude")
    if not claude_path:
        raise RuntimeError(
            "Claude Code CLI not found. Install it or use a different provider."
        )

    # Build a prompt that includes system context and asks for JSON output
    json_schema_str = json.dumps(_REQUIREMENT_SCHEMA, indent=2)

    prompt = f"""{SYSTEM_PROMPT}

{user_message}

IMPORTANT: Respond with ONLY a JSON object in this exact format — no markdown fences, no explanation, no other text:
{{"requirements": [...]}}

Each requirement in the array must match this schema:
{json_schema_str}

If no actionable requirements are found, return: {{"requirements": []}}"""

    cmd = [claude_path, "-p"]
    if model:
        cmd.extend(["--model", model])

    # Strip CLAUDECODE env var to allow running inside a Claude Code session
    env = {k: v for k, v in os.environ.items() if k != "CLAUDECODE"}

    result = subprocess.run(
        cmd,
        input=prompt,
        capture_output=True,
        text=True,
        timeout=120,
        env=env,
    )

    if result.returncode != 0:
        raise RuntimeError(
            f"Claude Code CLI failed (exit {result.returncode}): {result.stderr[:500]}"
        )

    output = result.stdout.strip()

    # Try to parse JSON from the output
    # Claude might wrap it in markdown fences despite instructions
    json_match = re.search(r'\{[\s\S]*"requirements"[\s\S]*\}', output)
    if not json_match:
        return []

    try:
        data = json.loads(json_match.group())
        return data.get("requirements", [])
    except json.JSONDecodeError:
        return []


# --- Main entry point ---

PROVIDERS = {"anthropic", "openai", "claude-code"}


def extract_requirements(
    articles: list[dict],
    product_context: str,
    provider: str = "anthropic",
    api_key: str | None = None,
    model: str | None = None,
) -> ExtractionResult:
    """Extract compliance requirements from retrieved articles using LLM.

    Args:
        articles: List of dicts from VectorStore.search(), each with
            'text', 'metadata', 'chunk_id', 'score'.
        product_context: Description of the product scenario,
            e.g. "Novel food insect protein bar with health claims".
        provider: LLM provider — "anthropic", "openai", or "claude-code".
        api_key: API key (for anthropic/openai). Falls back to env var.
        model: Model to use. None means use provider default.

    Returns:
        ExtractionResult with typed ComplianceRequirement objects.
    """
    if not articles:
        return ExtractionResult(articles_processed=0, product_context=product_context)

    if provider not in PROVIDERS:
        raise ValueError(f"Unknown provider '{provider}'. Choose from: {sorted(PROVIDERS)}")

    user_message = _build_user_message(articles, product_context)

    if provider == "anthropic":
        raw_reqs = _extract_anthropic(user_message, api_key=api_key, model=model)
    elif provider == "openai":
        raw_reqs = _extract_openai(user_message, api_key=api_key, model=model)
    elif provider == "claude-code":
        raw_reqs = _extract_claude_code(user_message, model=model)
    else:
        raw_reqs = []

    requirements = _parse_requirements(raw_reqs)

    return ExtractionResult(
        requirements=requirements,
        articles_processed=len(articles),
        product_context=product_context,
    )
