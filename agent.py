"""
agent.py

The FitFindr planning loop. Orchestrates the three tools in response to a
natural language user query, passing state between them via a session dict.

Complete tools.py and test each tool in isolation before implementing this file.

Usage (once implemented):
    from agent import run_agent
    from utils.data_loader import get_example_wardrobe

    result = run_agent(
        query="vintage graphic tee under $30, size M",
        wardrobe=get_example_wardrobe(),
    )
    print(result["fit_card"])
    print(result["error"])   # None on success
"""

from tools import (
    search_listings,
    suggest_outfit,
    create_fit_card,
    compare_price,
    check_trends,
    load_style_profile,
    update_style_profile,
)


# ── session state ─────────────────────────────────────────────────────────────

def _new_session(query: str, wardrobe: dict) -> dict:
    """
    Initialize and return a fresh session dict for one user interaction.

    The session dict is the single source of truth for everything that happens
    during a run — it stores the original query, parsed parameters, tool results,
    and any error that caused early termination.

    You may add fields to this dict as needed for your implementation.
    """
    return {
        "query": query,              # original user query
        "parsed": {},                # extracted description / size / max_price
        "search_results": [],        # list of matching listing dicts
        "selected_item": None,       # top result, passed into suggest_outfit
        "wardrobe": wardrobe,        # user's wardrobe dict
        "outfit_suggestion": None,   # string returned by suggest_outfit
        "fit_card": None,            # string returned by create_fit_card
        "error": None,               # set if the interaction ended early
        "search_fallbacks": [],       # notes about loosened search constraints
        "price_comparison": None,     # dict returned by compare_price
        "style_profile": {},          # local persistent style memory
        "style_profile_note": None,   # short display note about memory
        "trend_awareness": None,       # dict returned by check_trends
    }


# ── planning loop ─────────────────────────────────────────────────────────────

def run_agent(query: str, wardrobe: dict) -> dict:
    """
    Main agent entry point. Runs the FitFindr planning loop for a single
    user interaction and returns the completed session dict.

    Args:
        query:    Natural language user request
                  (e.g., "vintage graphic tee under $30, size M")
        wardrobe: User's wardrobe dict — use get_example_wardrobe() or
                  get_empty_wardrobe() from utils/data_loader.py

    Returns:
        The session dict after the interaction completes. Check session["error"]
        first — if it is not None, the interaction ended early and the other
        output fields (outfit_suggestion, fit_card) will be None.

    TODO — implement this function using the planning loop you designed in planning.md:

        Step 1: Initialize the session with _new_session().

        Step 2: Parse the user's query to extract a description, size, and
                max_price. You can use regex, string splitting, or ask the LLM
                to parse it — document your choice in planning.md.
                Store the result in session["parsed"].

        Step 3: Call search_listings() with the parsed parameters.
                Store results in session["search_results"].
                If no results: set session["error"] to a helpful message and
                return the session early. Do NOT proceed to suggest_outfit
                with empty input.

        Step 4: Select the item to use (e.g., the top result).
                Store it in session["selected_item"].

        Step 5: Call suggest_outfit() with the selected item and wardrobe.
                Store the result in session["outfit_suggestion"].

        Step 6: Call create_fit_card() with the outfit suggestion and selected item.
                Store the result in session["fit_card"].

        Step 7: Return the session.

    Before writing code, complete the Planning Loop and State Management sections
    of planning.md — your implementation should match what you described there.
    """
    import re

    session = _new_session(query, wardrobe)
    session["retry_count"] = 0
    session["style_profile"] = load_style_profile()

    def style_profile_note(profile: dict) -> str | None:
        remembered = []
        if profile.get("style_tags"):
            remembered.append(", ".join(profile["style_tags"][:4]))
        if profile.get("colors"):
            remembered.append("colors: " + ", ".join(profile["colors"][:3]))
        if not remembered:
            return "No saved style profile yet."
        return "Style memory used: " + "; ".join(remembered)

    search_text = (query or "").strip()
    first_sentence = re.split(r"[.!?]", search_text, maxsplit=1)[0]

    price_match = re.search(
        r"(?:\b(?:under|below|less than|up to)\s*\$?(\d+(?:\.\d{1,2})?)|\$(\d+(?:\.\d{1,2})?))",
        first_sentence,
        re.IGNORECASE,
    )
    max_price = float(next(group for group in price_match.groups() if group)) if price_match else None

    size = None
    size_match = re.search(
        r"\b(?:in\s+)?size\s+([a-z0-9./-]+)|"
        r"\b(XXXL|XXL|XL|XS|XXS|S/M|M/L|L/XL|XS/S|S|M|L|US\s*\d+(?:\.\d)?|W\d+(?:\s*L\d+)?)\b",
        first_sentence,
        re.IGNORECASE,
    )
    if size_match:
        size = next(group for group in size_match.groups() if group)
        size = re.sub(r"\s+", " ", size.upper()).strip()

    description = re.sub(
        r"(?:\b(?:under|below|less than|up to)\s*\$?\d+(?:\.\d{1,2})?|\$\d+(?:\.\d{1,2})?)",
        " ",
        first_sentence,
        flags=re.IGNORECASE,
    )
    description = re.sub(
        r"\b(?:in\s+)?size\s+[a-z0-9./-]+",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(
        r"\b(i'?m|i am|looking for|searching for|want|need|find me|show me)\b",
        " ",
        description,
        flags=re.IGNORECASE,
    )
    description = re.sub(r"[^a-zA-Z0-9\s/-]", " ", description)
    description = " ".join(description.split())

    session["parsed"] = {
        "description": description,
        "size": size,
        "max_price": max_price,
    }

    results = search_listings(description, size=size, max_price=max_price)

    if not results and size is not None:
        session["search_fallbacks"].append(
            f"No matches found in size {size}; removed the size filter."
        )
        results = search_listings(description, size=None, max_price=max_price)

    if not results and max_price is not None:
        session["search_fallbacks"].append(
            f"No matches found under ${max_price:.2f}; removed the price ceiling."
        )
        results = search_listings(description, size=None, max_price=None)

    session["search_results"] = results
    if not results:
        session["error"] = "No matching listings were found for that description and price range. Try a different search."
        return session

    session["selected_item"] = results[0]
    session["price_comparison"] = compare_price(session["selected_item"])
    session["trend_awareness"] = check_trends(
        description,
        size=size,
        item=session["selected_item"],
    )
    session["style_profile"] = update_style_profile(
        session["query"],
        session["selected_item"],
        session["wardrobe"],
    )
    session["style_profile_note"] = style_profile_note(session["style_profile"])

    wardrobe_context = dict(session["wardrobe"] or {})
    wardrobe_context["_style_profile"] = session["style_profile"]
    wardrobe_context["_trend_awareness"] = session["trend_awareness"]

    outfit = suggest_outfit(session["selected_item"], wardrobe_context)
    if not outfit or not outfit.strip():
        if len(results) < 2:
            session["error"] = "Unable to build a complete outfit with your wardrobe and available listings. Try a different search."
            return session

        session["retry_count"] = 1
        session["selected_item"] = results[1]
        session["price_comparison"] = compare_price(session["selected_item"])
        session["trend_awareness"] = check_trends(
            description,
            size=size,
            item=session["selected_item"],
        )
        session["style_profile"] = update_style_profile(
            session["query"],
            session["selected_item"],
            session["wardrobe"],
        )
        session["style_profile_note"] = style_profile_note(session["style_profile"])
        wardrobe_context = dict(session["wardrobe"] or {})
        wardrobe_context["_style_profile"] = session["style_profile"]
        wardrobe_context["_trend_awareness"] = session["trend_awareness"]
        outfit = suggest_outfit(session["selected_item"], wardrobe_context)

        if not outfit or not outfit.strip():
            session["error"] = "Unable to build a complete outfit with your wardrobe and available listings. Try a different search."
            return session

    session["outfit_suggestion"] = outfit

    fit_card = create_fit_card(session["outfit_suggestion"], session["selected_item"])
    if not fit_card or not fit_card.strip() or "outfit suggestion is empty" in fit_card.lower():
        session["error"] = "We created outfit suggestions but couldn't generate a caption. Try again or adjust your query."
        return session

    session["fit_card"] = fit_card
    return session


# ── CLI test ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from utils.data_loader import get_example_wardrobe, get_empty_wardrobe

    print("=== Happy path: graphic tee ===\n")
    session = run_agent(
        query="looking for a vintage graphic tee under $30",
        wardrobe=get_example_wardrobe(),
    )
    if session["error"]:
        print(f"Error: {session['error']}")
    else:
        print(f"Found: {session['selected_item']['title']}")
        print(f"\nOutfit: {session['outfit_suggestion']}")
        print(f"\nFit card: {session['fit_card']}")

    print("\n\n=== No-results path ===\n")
    session2 = run_agent(
        query="designer ballgown size XXS under $5",
        wardrobe=get_example_wardrobe(),
    )
    print(f"Error message: {session2['error']}")
