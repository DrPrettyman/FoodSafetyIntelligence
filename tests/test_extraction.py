"""
Tests for the LLM-based structured extraction module.

Tests cover:
1. Pydantic schema validation (ComplianceRequirement, ExtractionResult)
2. User message construction from articles
3. Provider dispatch and validation
4. Anthropic provider with mocked API
5. OpenAI provider with mocked API
6. Claude Code CLI provider with mocked subprocess
7. Edge cases: empty articles, malformed LLM output, missing API key
"""

import json
from unittest.mock import MagicMock, patch

import pytest

from src.extraction.schemas import (
    ComplianceRequirement,
    ExtractionResult,
    Priority,
    RequirementType,
)
from src.extraction.llm_extractor import (
    EXTRACTION_TOOL,
    FEW_SHOT_EXAMPLE,
    PROVIDERS,
    _build_user_message,
    _extract_claude_code,
    _parse_requirements,
    extract_requirements,
)


# --- Schema tests ---


class TestComplianceRequirement:
    """Tests for the ComplianceRequirement Pydantic model."""

    def test_valid_requirement(self):
        req = ComplianceRequirement(
            regulation_id="32015R2283",
            article_number=7,
            article_title="General conditions",
            requirement_summary="A novel food must be authorised before market placement.",
            requirement_type=RequirementType.AUTHORISATION,
            priority=Priority.BEFORE_LAUNCH,
            confidence=0.95,
        )
        assert req.regulation_id == "32015R2283"
        assert req.article_number == 7
        assert req.requirement_type == RequirementType.AUTHORISATION
        assert req.priority == Priority.BEFORE_LAUNCH
        assert req.confidence == 0.95

    def test_default_fields(self):
        req = ComplianceRequirement(
            regulation_id="32002R0178",
            article_number=14,
            article_title="Food safety requirements",
            requirement_summary="Food must be safe.",
            requirement_type=RequirementType.GENERAL_OBLIGATION,
            priority=Priority.ONGOING,
        )
        assert req.applicable_to == ""
        assert req.conditions == ""
        assert req.cross_references == []
        assert req.source_text_snippet == ""
        assert req.confidence == 0.0

    def test_all_fields(self):
        req = ComplianceRequirement(
            regulation_id="32015R2283",
            article_number=7,
            article_title="General conditions",
            requirement_summary="Novel food must be authorised.",
            requirement_type=RequirementType.AUTHORISATION,
            priority=Priority.BEFORE_LAUNCH,
            applicable_to="food business operators",
            conditions="only for novel foods",
            cross_references=["32002R0178", "32011R1169"],
            source_text_snippet="shall only authorise",
            confidence=0.9,
        )
        assert req.applicable_to == "food business operators"
        assert len(req.cross_references) == 2
        assert req.source_text_snippet == "shall only authorise"

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            ComplianceRequirement(
                regulation_id="32015R2283",
                article_number=1,
                article_title="Test",
                requirement_summary="Test",
                requirement_type=RequirementType.LABELLING,
                priority=Priority.ONGOING,
                confidence=1.5,
            )

        with pytest.raises(Exception):
            ComplianceRequirement(
                regulation_id="32015R2283",
                article_number=1,
                article_title="Test",
                requirement_summary="Test",
                requirement_type=RequirementType.LABELLING,
                priority=Priority.ONGOING,
                confidence=-0.1,
            )

    def test_requirement_type_values(self):
        expected = {
            "authorisation", "notification", "labelling", "safety_assessment",
            "max_limit", "documentation", "monitoring", "traceability",
            "hygiene", "prohibition", "general_obligation",
        }
        actual = {e.value for e in RequirementType}
        assert actual == expected

    def test_priority_values(self):
        expected = {"before_launch", "ongoing", "if_applicable"}
        actual = {e.value for e in Priority}
        assert actual == expected

    def test_from_string_enum_values(self):
        """LLM returns string values — Pydantic should coerce them to enums."""
        req = ComplianceRequirement(
            regulation_id="32015R2283",
            article_number=7,
            article_title="General conditions",
            requirement_summary="Must be authorised.",
            requirement_type="authorisation",
            priority="before_launch",
            confidence=0.9,
        )
        assert req.requirement_type == RequirementType.AUTHORISATION
        assert req.priority == Priority.BEFORE_LAUNCH


class TestExtractionResult:
    def test_empty_result(self):
        result = ExtractionResult(articles_processed=0, product_context="test")
        assert result.requirements == []
        assert result.articles_processed == 0
        assert result.product_context == "test"

    def test_with_requirements(self):
        req = ComplianceRequirement(
            regulation_id="32015R2283",
            article_number=7,
            article_title="General conditions",
            requirement_summary="Must be authorised.",
            requirement_type=RequirementType.AUTHORISATION,
            priority=Priority.BEFORE_LAUNCH,
            confidence=0.95,
        )
        result = ExtractionResult(
            requirements=[req],
            articles_processed=3,
            product_context="insect protein bar",
        )
        assert len(result.requirements) == 1
        assert result.articles_processed == 3


# --- User message construction ---


class TestBuildUserMessage:
    def test_basic_message(self):
        articles = [
            {"text": "Article 1: This is the scope of the regulation."},
            {"text": "Article 7: General conditions for placing novel foods on the market."},
        ]
        msg = _build_user_message(articles, "insect protein bar")
        assert "Product context: insect protein bar" in msg
        assert "--- ARTICLE 1 ---" in msg
        assert "--- ARTICLE 2 ---" in msg
        assert "Article 1: This is the scope" in msg
        assert "Article 7: General conditions" in msg

    def test_includes_few_shot_example(self):
        articles = [{"text": "Test article."}]
        msg = _build_user_message(articles, "test product")
        assert "--- FEW-SHOT EXAMPLE ---" in msg
        assert "--- END EXAMPLE ---" in msg
        assert FEW_SHOT_EXAMPLE["article_text"][:50] in msg

    def test_includes_extraction_instruction(self):
        articles = [{"text": "Test article."}]
        msg = _build_user_message(articles, "test product")
        assert "submit_requirements" in msg
        assert "actionable compliance requirements" in msg

    def test_empty_articles(self):
        msg = _build_user_message([], "test")
        assert "Product context: test" in msg
        assert "--- ARTICLE" not in msg


# --- Tool schema ---


class TestExtractionTool:
    def test_tool_has_required_fields(self):
        assert EXTRACTION_TOOL["name"] == "submit_requirements"
        schema = EXTRACTION_TOOL["input_schema"]
        assert schema["type"] == "object"
        assert "requirements" in schema["properties"]

    def test_tool_requirement_schema_matches_pydantic(self):
        item_schema = EXTRACTION_TOOL["input_schema"]["properties"]["requirements"]["items"]
        required = set(item_schema["required"])
        assert "regulation_id" in required
        assert "article_number" in required
        assert "requirement_summary" in required
        assert "requirement_type" in required
        assert "priority" in required
        assert "confidence" in required

    def test_tool_enum_values_match(self):
        item_props = EXTRACTION_TOOL["input_schema"]["properties"]["requirements"]["items"]["properties"]
        tool_req_types = set(item_props["requirement_type"]["enum"])
        python_req_types = {e.value for e in RequirementType}
        assert tool_req_types == python_req_types

        tool_priorities = set(item_props["priority"]["enum"])
        python_priorities = {e.value for e in Priority}
        assert tool_priorities == python_priorities


# --- Shared parsing ---


class TestParseRequirements:
    def test_valid_requirements(self):
        raw = [
            {
                "regulation_id": "32015R2283",
                "article_number": 7,
                "article_title": "General conditions",
                "requirement_summary": "Must be authorised.",
                "requirement_type": "authorisation",
                "priority": "before_launch",
                "confidence": 0.95,
            },
        ]
        reqs = _parse_requirements(raw)
        assert len(reqs) == 1
        assert reqs[0].regulation_id == "32015R2283"

    def test_malformed_skipped(self):
        raw = [
            # Valid
            {
                "regulation_id": "32015R2283",
                "article_number": 7,
                "article_title": "Good",
                "requirement_summary": "Good.",
                "requirement_type": "authorisation",
                "priority": "before_launch",
                "confidence": 0.9,
            },
            # Missing article_number
            {
                "regulation_id": "32015R2283",
                "article_title": "Bad",
                "requirement_summary": "Bad.",
                "requirement_type": "labelling",
                "priority": "ongoing",
                "confidence": 0.5,
            },
        ]
        reqs = _parse_requirements(raw)
        assert len(reqs) == 1


# --- Provider dispatch ---


class TestProviderDispatch:
    def test_unknown_provider_raises(self):
        articles = [{"text": "Test.", "metadata": {}, "chunk_id": "1", "score": 0.9}]
        with pytest.raises(ValueError, match="Unknown provider"):
            extract_requirements(articles, "test", provider="nonexistent")

    def test_providers_set(self):
        assert PROVIDERS == {"anthropic", "openai", "claude-code"}

    def test_empty_articles_returns_empty_any_provider(self):
        for provider in PROVIDERS:
            result = extract_requirements([], "test", provider=provider)
            assert result.requirements == []
            assert result.articles_processed == 0


# --- Anthropic provider (mocked) ---


def _make_mock_anthropic_response(requirements_data: list[dict]) -> MagicMock:
    """Build a mock Anthropic response with tool_use blocks."""
    tool_block = MagicMock()
    tool_block.type = "tool_use"
    tool_block.name = "submit_requirements"
    tool_block.input = {"requirements": requirements_data}

    response = MagicMock()
    response.content = [tool_block]
    return response


SAMPLE_REQS = [
    {
        "regulation_id": "32015R2283",
        "article_number": 7,
        "article_title": "General conditions",
        "requirement_summary": "Novel food must be authorised before market placement.",
        "requirement_type": "authorisation",
        "priority": "before_launch",
        "applicable_to": "food business operators",
        "conditions": "",
        "cross_references": ["32002R0178"],
        "source_text_snippet": "shall only authorise",
        "confidence": 0.95,
    },
]

SAMPLE_ARTICLES = [
    {"text": "Article 7 text...", "metadata": {"celex_id": "32015R2283"}, "chunk_id": "c1", "score": 0.9},
]


class TestAnthropicProvider:
    @patch("src.extraction.llm_extractor.anthropic.Anthropic")
    def test_successful_extraction(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_anthropic_response(SAMPLE_REQS)

        result = extract_requirements(SAMPLE_ARTICLES, "insect protein bar",
                                      provider="anthropic", api_key="test-key")

        assert result.articles_processed == 1
        assert len(result.requirements) == 1
        assert result.requirements[0].regulation_id == "32015R2283"
        assert result.requirements[0].requirement_type == RequirementType.AUTHORISATION

    @patch("src.extraction.llm_extractor.anthropic.Anthropic")
    def test_api_called_with_correct_params(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_anthropic_response([])

        extract_requirements(SAMPLE_ARTICLES, "test", provider="anthropic", api_key="test-key")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-sonnet-4-20250514"
        assert "regulatory compliance analyst" in call_kwargs["system"]
        assert call_kwargs["tools"] == [EXTRACTION_TOOL]
        assert call_kwargs["tool_choice"] == {"type": "tool", "name": "submit_requirements"}

    def test_no_api_key_raises(self):
        with patch.dict("os.environ", {}, clear=True):
            with pytest.raises(ValueError, match="No API key"):
                extract_requirements(SAMPLE_ARTICLES, "test", provider="anthropic", api_key=None)

    @patch("src.extraction.llm_extractor.anthropic.Anthropic")
    def test_uses_env_var_api_key(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_anthropic_response([])

        with patch.dict("os.environ", {"ANTHROPIC_API_KEY": "env-key"}):
            extract_requirements(SAMPLE_ARTICLES, "test", provider="anthropic")

        mock_anthropic_cls.assert_called_once_with(api_key="env-key")

    @patch("src.extraction.llm_extractor.anthropic.Anthropic")
    def test_malformed_requirement_skipped(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_client.messages.create.return_value = _make_mock_anthropic_response([
            SAMPLE_REQS[0],
            {"regulation_id": "bad", "requirement_type": "totally_made_up"},  # malformed
        ])

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="anthropic", api_key="key")
        assert len(result.requirements) == 1

    @patch("src.extraction.llm_extractor.anthropic.Anthropic")
    def test_multiple_content_blocks(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        text_block = MagicMock()
        text_block.type = "text"
        tool_block = MagicMock()
        tool_block.type = "tool_use"
        tool_block.name = "submit_requirements"
        tool_block.input = {"requirements": SAMPLE_REQS}

        response = MagicMock()
        response.content = [text_block, tool_block]
        mock_client.messages.create.return_value = response

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="anthropic", api_key="key")
        assert len(result.requirements) == 1

    @patch("src.extraction.llm_extractor.anthropic.Anthropic")
    def test_custom_model(self, mock_anthropic_cls):
        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.create.return_value = _make_mock_anthropic_response([])

        extract_requirements(SAMPLE_ARTICLES, "test", provider="anthropic",
                             api_key="key", model="claude-haiku-4-5-20251001")

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs["model"] == "claude-haiku-4-5-20251001"


# --- OpenAI provider (mocked) ---


class TestOpenAIProvider:
    def _make_mock_openai_response(self, requirements_data: list[dict]) -> MagicMock:
        tool_call = MagicMock()
        tool_call.function.name = "submit_requirements"
        tool_call.function.arguments = json.dumps({"requirements": requirements_data})

        message = MagicMock()
        message.tool_calls = [tool_call]

        choice = MagicMock()
        choice.message = message

        response = MagicMock()
        response.choices = [choice]
        return response

    @patch("src.extraction.llm_extractor.openai", create=True)
    def test_successful_extraction(self, mock_openai_module):
        # Mock the lazy import inside _extract_openai
        mock_client = MagicMock()
        mock_openai_module.OpenAI.return_value = mock_client
        mock_client.chat.completions.create.return_value = self._make_mock_openai_response(SAMPLE_REQS)

        # Patch the import statement inside _extract_openai
        import src.extraction.llm_extractor as extractor_mod
        with patch.dict("sys.modules", {"openai": mock_openai_module}):
            result = extract_requirements(SAMPLE_ARTICLES, "test",
                                          provider="openai", api_key="test-key")

        assert len(result.requirements) == 1
        assert result.requirements[0].regulation_id == "32015R2283"

    def test_no_api_key_raises(self):
        # Create a fake openai module that doesn't raise ImportError
        mock_openai = MagicMock()
        with patch.dict("sys.modules", {"openai": mock_openai}):
            with patch.dict("os.environ", {}, clear=True):
                with pytest.raises(ValueError, match="No API key"):
                    extract_requirements(SAMPLE_ARTICLES, "test",
                                         provider="openai", api_key=None)


# --- Claude Code CLI provider (mocked subprocess) ---


class TestClaudeCodeProvider:
    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_successful_extraction(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"requirements": SAMPLE_REQS}),
            stderr="",
        )

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")

        assert len(result.requirements) == 1
        assert result.requirements[0].regulation_id == "32015R2283"
        assert result.requirements[0].requirement_type == RequirementType.AUTHORISATION

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_handles_markdown_fenced_json(self, mock_run, mock_which):
        """Claude Code might wrap JSON in markdown fences despite instructions."""
        output = '```json\n' + json.dumps({"requirements": SAMPLE_REQS}) + '\n```'
        mock_run.return_value = MagicMock(returncode=0, stdout=output, stderr="")

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")
        assert len(result.requirements) == 1

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_handles_preamble_text(self, mock_run, mock_which):
        """Claude Code might add text before the JSON."""
        output = 'Here are the requirements:\n\n' + json.dumps({"requirements": SAMPLE_REQS})
        mock_run.return_value = MagicMock(returncode=0, stdout=output, stderr="")

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")
        assert len(result.requirements) == 1

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_no_requirements_found(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"requirements": []}),
            stderr="",
        )

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")
        assert result.requirements == []
        assert result.articles_processed == 1

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_unparseable_output(self, mock_run, mock_which):
        """If Claude Code returns garbage, should return empty list, not crash."""
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout="I don't understand the question.",
            stderr="",
        )

        result = extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")
        assert result.requirements == []

    @patch("src.extraction.llm_extractor.shutil.which", return_value=None)
    def test_claude_not_found_raises(self, mock_which):
        with pytest.raises(RuntimeError, match="Claude Code CLI not found"):
            extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_nonzero_exit_raises(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=1,
            stdout="",
            stderr="Error: something went wrong",
        )

        with pytest.raises(RuntimeError, match="Claude Code CLI failed"):
            extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_subprocess_called_correctly(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"requirements": []}),
            stderr="",
        )

        extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code")

        mock_run.assert_called_once()
        call_kwargs = mock_run.call_args
        cmd = call_kwargs.args[0] if call_kwargs.args else call_kwargs.kwargs.get("args", [])
        assert cmd[0] == "/usr/bin/claude"
        assert "-p" in cmd
        assert call_kwargs.kwargs.get("timeout") == 120

    @patch("src.extraction.llm_extractor.shutil.which", return_value="/usr/bin/claude")
    @patch("src.extraction.llm_extractor.subprocess.run")
    def test_custom_model_passed(self, mock_run, mock_which):
        mock_run.return_value = MagicMock(
            returncode=0,
            stdout=json.dumps({"requirements": []}),
            stderr="",
        )

        extract_requirements(SAMPLE_ARTICLES, "test", provider="claude-code", model="sonnet")

        cmd = mock_run.call_args.args[0]
        assert "--model" in cmd
        assert "sonnet" in cmd
