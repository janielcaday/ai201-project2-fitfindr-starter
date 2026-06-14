import pytest
from unittest.mock import patch, MagicMock

from tools import search_listings, suggest_outfit, create_fit_card
from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

# Run via command: .venv/bin/pytest tests/test_tools.py -v

# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def sample_item():
    return search_listings("vintage denim jacket")[0]

@pytest.fixture
def example_wardrobe():
    return get_example_wardrobe()

@pytest.fixture
def empty_wardrobe():
    return get_empty_wardrobe()

def _mock_groq(text: str):
    mock_client = MagicMock()
    mock_client.chat.completions.create.return_value = MagicMock(
        choices=[MagicMock(message=MagicMock(content=text))]
    )
    return mock_client


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)

def test_search_price_filter_inclusive():
    results = search_listings("jacket", max_price=45.0)
    assert all(item["price"] <= 45.0 for item in results)

def test_search_size_filter_case_insensitive():
    # "m" should match listings with size "S/M", "M", "M/L", etc.
    results = search_listings("top", size="m")
    assert all("m" in item["size"].lower() for item in results)

def test_search_size_filter_none_skips_filtering():
    results_no_size = search_listings("jacket", size=None)
    results_with_size = search_listings("jacket", size="L")
    assert len(results_no_size) >= len(results_with_size)

def test_search_sorted_by_relevance():
    results = search_listings("vintage denim blue jeans")
    assert len(results) > 1
    # first result should score >= second
    def score(listing):
        keywords = set("vintage denim blue jeans".lower().split())
        searchable = " ".join([
            listing["title"], listing["description"], listing["category"],
            " ".join(listing["style_tags"]), " ".join(listing["colors"]),
            listing["brand"] or "",
        ]).lower()
        return sum(1 for kw in keywords if kw in searchable)
    scores = [score(r) for r in results]
    assert scores == sorted(scores, reverse=True)

def test_search_result_has_required_fields():
    results = search_listings("jacket")
    for item in results:
        for field in ("id", "title", "description", "category", "style_tags",
                      "size", "condition", "price", "colors", "brand", "platform"):
            assert field in item

def test_search_combined_filters():
    results = search_listings("top", size="s", max_price=25)
    assert all(item["price"] <= 25 for item in results)
    assert all("s" in item["size"].lower() for item in results)

def test_search_no_zero_score_results():
    # every returned listing must match at least one keyword
    results = search_listings("denim")
    for item in results:
        searchable = " ".join([
            item["title"], item["description"], item["category"],
            " ".join(item["style_tags"]), " ".join(item["colors"]),
            item["brand"] or "",
        ]).lower()
        assert "denim" in searchable


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def test_suggest_outfit_returns_string(sample_item, example_wardrobe):
    with patch("tools._get_groq_client", return_value=_mock_groq("Outfit 1: jeans + tee")):
        result = suggest_outfit(sample_item, example_wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe_no_crash(sample_item, empty_wardrobe):
    with patch("tools._get_groq_client", return_value=_mock_groq("General styling advice here.")):
        result = suggest_outfit(sample_item, empty_wardrobe)
    assert isinstance(result, str)
    assert len(result) > 0

def test_suggest_outfit_empty_wardrobe_calls_llm(sample_item, empty_wardrobe):
    mock_client = _mock_groq("General styling advice.")
    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(sample_item, empty_wardrobe)
    mock_client.chat.completions.create.assert_called_once()

def test_suggest_outfit_wardrobe_prompt_references_items(sample_item, example_wardrobe):
    captured = {}
    mock_client = _mock_groq("Outfit suggestion.")
    def capture_call(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return MagicMock(choices=[MagicMock(message=MagicMock(content="Outfit suggestion."))])
    mock_client.chat.completions.create.side_effect = capture_call

    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(sample_item, example_wardrobe)

    prompt_text = captured["messages"][0]["content"]
    assert example_wardrobe["items"][0]["name"] in prompt_text

def test_suggest_outfit_includes_item_title(sample_item, example_wardrobe):
    captured = {}
    mock_client = _mock_groq("Outfit suggestion.")
    def capture_call(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return MagicMock(choices=[MagicMock(message=MagicMock(content="Outfit suggestion."))])
    mock_client.chat.completions.create.side_effect = capture_call

    with patch("tools._get_groq_client", return_value=mock_client):
        suggest_outfit(sample_item, example_wardrobe)

    prompt_text = captured["messages"][0]["content"]
    assert sample_item["title"] in prompt_text

def test_suggest_outfit_missing_items_key(sample_item):
    # wardrobe dict with no 'items' key treated same as empty
    with patch("tools._get_groq_client", return_value=_mock_groq("Advice.")):
        result = suggest_outfit(sample_item, {})
    assert isinstance(result, str)
    assert len(result) > 0


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def test_create_fit_card_returns_string(sample_item):
    with patch("tools._get_groq_client", return_value=_mock_groq("Thrifted this gem for $42!")):
        result = create_fit_card("Jeans + white tee + sneakers", sample_item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_empty_outfit_no_crash(sample_item):
    result = create_fit_card("", sample_item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_whitespace_outfit_no_crash(sample_item):
    result = create_fit_card("   ", sample_item)
    assert isinstance(result, str)
    assert len(result) > 0

def test_create_fit_card_empty_outfit_no_llm_call(sample_item):
    mock_client = _mock_groq("Should not be called.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card("", sample_item)
    mock_client.chat.completions.create.assert_not_called()

def test_create_fit_card_prompt_includes_item_details(sample_item):
    captured = {}
    mock_client = _mock_groq("Caption.")
    def capture_call(**kwargs):
        captured["messages"] = kwargs.get("messages", [])
        return MagicMock(choices=[MagicMock(message=MagicMock(content="Caption."))])
    mock_client.chat.completions.create.side_effect = capture_call

    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card("Jeans + tee", sample_item)

    prompt_text = captured["messages"][0]["content"]
    assert sample_item["title"] in prompt_text
    assert str(sample_item["price"]) in prompt_text
    assert sample_item["platform"] in prompt_text

def test_create_fit_card_uses_high_temperature(sample_item):
    mock_client = _mock_groq("Caption.")
    with patch("tools._get_groq_client", return_value=mock_client):
        create_fit_card("Jeans + tee", sample_item)
    call_kwargs = mock_client.chat.completions.create.call_args
    assert call_kwargs.kwargs.get("temperature", 0) >= 0.9

def test_create_fit_card_empty_outfit_mentions_category(sample_item):
    result = create_fit_card("", sample_item)
    assert sample_item["category"] in result or sample_item["title"] in result
