"""
Pydantic schemas for structured compliance requirement extraction.

These schemas define the typed output that the LLM produces from
retrieved regulatory articles. Each field maps to a specific aspect
of a regulatory requirement that a compliance officer needs.
"""

from enum import Enum

from pydantic import BaseModel, Field


class RequirementType(str, Enum):
    """Categories of regulatory requirements."""

    AUTHORISATION = "authorisation"  # must obtain approval before market
    NOTIFICATION = "notification"  # must notify authority
    LABELLING = "labelling"  # labelling/information requirements
    SAFETY_ASSESSMENT = "safety_assessment"  # requires safety evaluation
    MAX_LIMIT = "max_limit"  # maximum permitted level (additive, contaminant, etc.)
    DOCUMENTATION = "documentation"  # record-keeping, dossier requirements
    MONITORING = "monitoring"  # post-market monitoring, ongoing surveillance
    TRACEABILITY = "traceability"  # traceability requirements
    HYGIENE = "hygiene"  # hygiene and process requirements
    PROHIBITION = "prohibition"  # something is banned/restricted
    GENERAL_OBLIGATION = "general_obligation"  # catch-all for other requirements


class Priority(str, Enum):
    """When in the product lifecycle this requirement applies."""

    BEFORE_LAUNCH = "before_launch"  # must do before placing on market
    ONGOING = "ongoing"  # continuous obligation while product is on market
    IF_APPLICABLE = "if_applicable"  # only if certain conditions are met


class ComplianceRequirement(BaseModel):
    """A single regulatory requirement extracted from an article."""

    regulation_id: str = Field(
        description="CELEX number of the source regulation, e.g. '32015R2283'"
    )
    article_number: int = Field(
        description="Article number where this requirement is stated"
    )
    article_title: str = Field(
        description="Title of the article, e.g. 'General conditions for inclusion'"
    )
    requirement_summary: str = Field(
        description="Plain-English summary of what must be done (1-2 sentences)"
    )
    requirement_type: RequirementType = Field(
        description="Category of the requirement"
    )
    priority: Priority = Field(
        description="When this requirement applies in the product lifecycle"
    )
    applicable_to: str = Field(
        default="",
        description="Who or what this applies to, e.g. 'food business operators placing novel foods on the market'"
    )
    conditions: str = Field(
        default="",
        description="Conditions under which this requirement applies, if not universal"
    )
    cross_references: list[str] = Field(
        default_factory=list,
        description="CELEX numbers of other regulations referenced in this requirement"
    )
    source_text_snippet: str = Field(
        default="",
        description="Key phrase from the source text supporting this requirement (for citation)"
    )
    confidence: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="LLM's self-assessed confidence in this extraction (0-1)"
    )


class ExtractionResult(BaseModel):
    """Result of extracting requirements from a set of retrieved articles."""

    requirements: list[ComplianceRequirement] = Field(default_factory=list)
    articles_processed: int = Field(default=0)
    product_context: str = Field(
        default="",
        description="The product scenario that triggered this extraction"
    )
