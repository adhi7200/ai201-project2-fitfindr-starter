
import tools
from tools import (
    compare_price,
    create_fit_card,
    load_style_profile,
    search_listings,
    suggest_outfit,
    update_style_profile,
)
from utils.data_loader import get_empty_wardrobe, get_example_wardrobe

def test_search_returns_results():
    results = search_listings("vintage graphic tee", size=None, max_price=50)
    assert isinstance(results, list)
    assert len(results) > 0

def test_search_empty_results():
    results = search_listings("designer ballgown", size="XXS", max_price=5)
    assert results == []   # empty list, no exception

def test_search_price_filter():
    results = search_listings("jacket", size=None, max_price=10)
    assert all(item["price"] <= 10 for item in results)


def test_suggest_outfit_with_empty_wardrobe(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            class Message:
                content = "Pair it with straight-leg jeans and white sneakers."

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(tools, "_get_groq_client", lambda: FakeClient())

    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_empty_wardrobe())

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "jeans" in result.lower()


def test_suggest_outfit_with_example_wardrobe(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            class Message:
                content = "Use the new tee with Baggy straight-leg jeans and Black combat boots."

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(tools, "_get_groq_client", lambda: FakeClient())

    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = suggest_outfit(item, get_example_wardrobe())

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "baggy straight-leg jeans" in result.lower()


def test_create_fit_card_empty_outfit():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("", item)

    assert isinstance(result, str)
    assert "outfit suggestion is empty" in result.lower()


def test_create_fit_card_returns_caption(monkeypatch):
    class FakeCompletions:
        def create(self, **kwargs):
            class Message:
                content = "Found this tee on depop for $18 and styled it with relaxed denim."

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(tools, "_get_groq_client", lambda: FakeClient())

    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = create_fit_card("Pair it with baggy jeans and sneakers.", item)

    assert isinstance(result, str)
    assert result.strip() != ""
    assert "depop" in result.lower()


def test_compare_price_returns_price_context():
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    result = compare_price(item)

    assert result["selected_price"] == item["price"]
    assert result["verdict"] in {"good deal", "fair price", "pricey", "not enough data"}
    assert "explanation" in result
    assert isinstance(result["comparable_count"], int)


def test_compare_price_handles_no_comparables(monkeypatch):
    item = {
        "id": "only_item",
        "title": "One-off cape",
        "description": "A one of one piece",
        "category": "costume",
        "style_tags": ["rare"],
        "size": "M",
        "condition": "good",
        "price": 99.0,
        "colors": ["silver"],
        "brand": None,
        "platform": "depop",
    }
    monkeypatch.setattr(tools, "load_listings", lambda: [item])

    result = compare_price(item)

    assert result["verdict"] == "not enough data"
    assert result["comparable_count"] == 0


def test_style_profile_loads_default_when_missing(tmp_path, monkeypatch):
    memory_path = tmp_path / "style_profile_memory.json"
    monkeypatch.setattr(tools, "STYLE_PROFILE_PATH", str(memory_path))

    profile = load_style_profile()

    assert profile["style_tags"] == []
    assert profile["colors"] == []
    assert profile["recent_queries"] == []


def test_update_style_profile_persists_selected_item(tmp_path, monkeypatch):
    memory_path = tmp_path / "style_profile_memory.json"
    monkeypatch.setattr(tools, "STYLE_PROFILE_PATH", str(memory_path))
    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]

    profile = update_style_profile("vintage graphic tee under $50", item, get_example_wardrobe())
    loaded_profile = load_style_profile()

    assert item["id"] in profile["last_selected_item_ids"]
    assert item["category"] in loaded_profile["categories"]
    assert any(tag in loaded_profile["style_tags"] for tag in item["style_tags"])


def test_suggest_outfit_includes_style_profile_memory(monkeypatch):
    captured = {}

    class FakeCompletions:
        def create(self, **kwargs):
            captured["prompt"] = kwargs["messages"][1]["content"]

            class Message:
                content = "Style it with remembered vintage pieces."

            class Choice:
                message = Message()

            class Response:
                choices = [Choice()]

            return Response()

    class FakeChat:
        completions = FakeCompletions()

    class FakeClient:
        chat = FakeChat()

    monkeypatch.setattr(tools, "_get_groq_client", lambda: FakeClient())

    item = search_listings("vintage graphic tee", size=None, max_price=50)[0]
    wardrobe = get_example_wardrobe()
    wardrobe["_style_profile"] = {
        "style_tags": ["vintage", "streetwear"],
        "colors": ["black"],
        "categories": ["tops"],
        "recent_queries": [],
        "last_selected_item_ids": [],
    }
    result = suggest_outfit(item, wardrobe)

    assert result.strip() != ""
    assert "Style profile memory" in captured["prompt"]
    assert "vintage" in captured["prompt"]
