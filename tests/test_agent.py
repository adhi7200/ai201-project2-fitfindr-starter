import agent
from agent import run_agent
from utils.data_loader import get_example_wardrobe


def test_run_agent_retries_search_without_size(monkeypatch):
    item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "description": "A test tee",
        "category": "tops",
        "style_tags": ["graphic tee", "streetwear"],
        "size": "L",
        "condition": "good",
        "price": 20.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }
    calls = []

    def fake_search(description, size=None, max_price=None):
        calls.append((description, size, max_price))
        if size is not None:
            return []
        return [item]

    monkeypatch.setattr(agent, "search_listings", fake_search)
    monkeypatch.setattr(agent, "compare_price", lambda selected: {"verdict": "fair price"})
    monkeypatch.setattr(agent, "load_style_profile", lambda: {"style_tags": [], "colors": [], "categories": []})
    monkeypatch.setattr(agent, "update_style_profile", lambda query, selected, wardrobe: {
        "style_tags": selected["style_tags"],
        "colors": selected["colors"],
        "categories": [selected["category"]],
    })
    monkeypatch.setattr(agent, "suggest_outfit", lambda selected, wardrobe: "Wear it with jeans.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, selected: "A relaxed thrifted fit.")

    session = run_agent("graphic tee size M under $25", get_example_wardrobe())

    assert session["error"] is None
    assert session["selected_item"] == item
    assert session["search_fallbacks"] == ["No matches found in size M; removed the size filter."]
    assert calls[0][1] == "M"
    assert calls[1][1] is None


def test_run_agent_search_fallback_can_still_fail(monkeypatch):
    monkeypatch.setattr(agent, "search_listings", lambda *args, **kwargs: [])
    monkeypatch.setattr(agent, "load_style_profile", lambda: {"style_tags": [], "colors": [], "categories": []})

    session = run_agent("designer ballgown size XXS under $5", get_example_wardrobe())

    assert session["error"] == "No matching listings were found for that description and price range. Try a different search."
    assert session["selected_item"] is None
    assert session["search_fallbacks"] == [
        "No matches found in size XXS; removed the size filter.",
        "No matches found under $5.00; removed the price ceiling.",
    ]


def test_run_agent_stores_style_profile_note(monkeypatch):
    item = {
        "id": "lst_test",
        "title": "Test Graphic Tee",
        "description": "A test tee",
        "category": "tops",
        "style_tags": ["graphic tee", "streetwear"],
        "size": "M",
        "condition": "good",
        "price": 20.0,
        "colors": ["black"],
        "brand": None,
        "platform": "depop",
    }

    monkeypatch.setattr(agent, "search_listings", lambda *args, **kwargs: [item])
    monkeypatch.setattr(agent, "compare_price", lambda selected: {"verdict": "fair price"})
    monkeypatch.setattr(agent, "load_style_profile", lambda: {"style_tags": [], "colors": [], "categories": []})
    monkeypatch.setattr(agent, "update_style_profile", lambda query, selected, wardrobe: {
        "style_tags": ["streetwear"],
        "colors": ["black"],
        "categories": ["tops"],
    })
    monkeypatch.setattr(agent, "suggest_outfit", lambda selected, wardrobe: "Wear it with jeans.")
    monkeypatch.setattr(agent, "create_fit_card", lambda outfit, selected: "A relaxed thrifted fit.")

    session = run_agent("graphic tee under $25", get_example_wardrobe())

    assert session["style_profile"]["style_tags"] == ["streetwear"]
    assert "Style memory used" in session["style_profile_note"]
