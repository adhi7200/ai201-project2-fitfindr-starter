"""
tools.py

The three required FitFindr tools. Each tool is a standalone function that
can be called and tested independently before being wired into the agent loop.

Complete and test each tool before moving to agent.py.

Tools:
    search_listings(description, size, max_price)  → list[dict]
    suggest_outfit(new_item, wardrobe)              → str
    create_fit_card(outfit, new_item)               → str
"""

import json
import os

from dotenv import load_dotenv
from groq import Groq

from utils.data_loader import load_listings

load_dotenv()

STYLE_PROFILE_PATH = os.path.join(
    os.path.dirname(__file__),
    "data",
    "style_profile_memory.json",
)

DEFAULT_STYLE_PROFILE = {
    "style_tags": [],
    "colors": [],
    "categories": [],
    "recent_queries": [],
    "last_selected_item_ids": [],
}


# ── Groq client ───────────────────────────────────────────────────────────────

def _get_groq_client():
    """Initialize and return a Groq client using GROQ_API_KEY from .env."""
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        raise ValueError(
            "GROQ_API_KEY not set. Add it to a .env file in the project root."
        )
    return Groq(api_key=api_key)


# ── Tool 1: search_listings ───────────────────────────────────────────────────

def search_listings(
    description: str,
    size: str | None = None,
    max_price: float | None = None,
) -> list[dict]:
    """
    Search the mock listings dataset for items matching the description,
    optional size, and optional price ceiling.

    Args:
        description: Keywords describing what the user is looking for
                     (e.g., "vintage graphic tee").
        size:        Size string to filter by, or None to skip size filtering.
                     Matching is case-insensitive (e.g., "M" matches "S/M").
        max_price:   Maximum price (inclusive), or None to skip price filtering.

    Returns:
        A list of matching listing dicts, sorted by relevance (best match first).
        Returns an empty list if nothing matches — does NOT raise an exception.

    Each listing dict has the following fields:
        id, title, description, category, style_tags (list), size,
        condition, price (float), colors (list), brand, platform

    TODO:
        1. Load all listings with load_listings().
        2. Filter by max_price and size (if provided).
        3. Score each remaining listing by keyword overlap with `description`.
        4. Drop any listings with a score of 0 (no relevant matches).
        5. Sort by score, highest first, and return the listing dicts.

    Before writing code, fill in the Tool 1 section of planning.md.
    """
    import re

    if not description or not description.strip():
        return []

    stop_words = {
        "a", "an", "and", "for", "i", "in", "is", "looking", "of", "or",
        "the", "to", "under", "want", "with",
    }

    def normalize_words(text: str) -> list[str]:
        return [
            word
            for word in re.findall(r"[a-z0-9]+", text.lower())
            if word not in stop_words
        ]

    query_words = normalize_words(description)
    if not query_words:
        return []

    scored_results = []
    normalized_size = size.lower().strip() if size else None

    for listing in load_listings():
        if max_price is not None and listing.get("price", 0) > max_price:
            continue

        listing_size = str(listing.get("size", "")).lower()
        if normalized_size and normalized_size not in listing_size:
            continue

        searchable_parts = [
            listing.get("title", ""),
            listing.get("description", ""),
            listing.get("category", ""),
            " ".join(listing.get("style_tags", [])),
            " ".join(listing.get("colors", [])),
            listing.get("brand") or "",
        ]
        searchable_text = " ".join(searchable_parts).lower()
        searchable_words = set(normalize_words(searchable_text))

        score = sum(1 for word in query_words if word in searchable_words)
        if description.lower().strip() in searchable_text:
            score += 2
        for tag in listing.get("style_tags", []):
            if tag.lower() in description.lower():
                score += 2

        if score > 0:
            scored_results.append((score, listing))

    scored_results.sort(key=lambda result: (-result[0], result[1].get("price", 0)))
    return [listing for _, listing in scored_results[:3]]


# ── Tool 2: suggest_outfit ────────────────────────────────────────────────────

def suggest_outfit(new_item: dict, wardrobe: dict) -> str:
    """
    Given a thrifted item and the user's wardrobe, suggest 1–2 complete outfits.

    Args:
        new_item: A listing dict (the item the user is considering buying).
        wardrobe: A wardrobe dict with an 'items' key containing a list of
                  wardrobe item dicts. May be empty — handle this gracefully.

    Returns:
        A non-empty string with outfit suggestions.
        If the wardrobe is empty, offer general styling advice for the item
        rather than raising an exception or returning an empty string.

    TODO:
        1. Check whether wardrobe['items'] is empty.
        2. If empty: call the LLM with a prompt for general styling ideas
           (what kinds of items pair well, what vibe it suits, etc.).
        3. If not empty: format the wardrobe items into a prompt and ask
           the LLM to suggest specific outfit combinations using the new item
           and named pieces from the wardrobe.
        4. Return the LLM's response as a string.

    Before writing code, fill in the Tool 2 section of planning.md.
    """
    if not new_item:
        return ""

    wardrobe_context = wardrobe or {}
    wardrobe_items = wardrobe_context.get("items", [])
    style_profile = wardrobe_context.get("_style_profile") or {}
    item_summary = (
        f"{new_item.get('title', 'Selected item')} "
        f"({new_item.get('category', 'unknown category')}, "
        f"size {new_item.get('size', 'unknown')}, "
        f"{', '.join(new_item.get('colors', []))}, "
        f"tags: {', '.join(new_item.get('style_tags', []))}, "
        f"${new_item.get('price', 'unknown')} on {new_item.get('platform', 'unknown')})"
    )
    profile_parts = []
    if style_profile.get("style_tags"):
        profile_parts.append(f"remembered style tags: {', '.join(style_profile['style_tags'][:5])}")
    if style_profile.get("colors"):
        profile_parts.append(f"remembered colors: {', '.join(style_profile['colors'][:5])}")
    if style_profile.get("categories"):
        profile_parts.append(f"remembered categories: {', '.join(style_profile['categories'][:3])}")
    profile_text = ""
    if profile_parts:
        profile_text = "\nStyle profile memory:\n" + "; ".join(profile_parts) + "\n"

    if wardrobe_items:
        wardrobe_text = "\n".join(
            "- "
            f"{item.get('name', 'Unnamed item')} "
            f"({item.get('category', 'unknown')}; "
            f"colors: {', '.join(item.get('colors', []))}; "
            f"tags: {', '.join(item.get('style_tags', []))}; "
            f"notes: {item.get('notes') or 'none'})"
            for item in wardrobe_items
        )
        user_prompt = (
            "New thrifted item:\n"
            f"{item_summary}\n\n"
            "User wardrobe:\n"
            f"{wardrobe_text}\n\n"
            f"{profile_text}"
            "Suggest 1-2 complete outfits that use the new item and named "
            "pieces from the wardrobe. Include why the colors, silhouette, "
            "and style work together. Keep it practical and specific."
        )
    else:
        user_prompt = (
            "New thrifted item:\n"
            f"{item_summary}\n\n"
            f"{profile_text}"
            "The user has not added wardrobe items yet. Suggest 1-2 ways to "
            "style this item using common basics, including colors, silhouettes, "
            "shoes, and accessories that would work well."
        )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are FitFindr, a concise secondhand fashion stylist. "
                        "Write useful outfit suggestions, not shopping ads."
                    ),
                },
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.8,
            max_tokens=450,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""


def compare_price(item: dict) -> dict:
    """
    Estimate whether the selected listing is a good deal, fair price, or pricey
    compared with similar items in the mock listings dataset.
    """
    if not item or item.get("price") is None:
        return {
            "selected_price": None,
            "average_price": None,
            "median_price": None,
            "comparable_count": 0,
            "verdict": "not enough data",
            "explanation": "No selected item price was available to compare.",
        }

    selected_price = float(item["price"])
    item_tags = set(item.get("style_tags", []))
    item_colors = set(item.get("colors", []))

    comparables = []
    for listing in load_listings():
        if listing.get("id") == item.get("id"):
            continue
        if listing.get("category") != item.get("category"):
            continue

        listing_tags = set(listing.get("style_tags", []))
        listing_colors = set(listing.get("colors", []))
        if item_tags & listing_tags or item_colors & listing_colors:
            comparables.append(listing)

    if not comparables:
        comparables = [
            listing
            for listing in load_listings()
            if listing.get("id") != item.get("id")
            and listing.get("category") == item.get("category")
        ]

    prices = sorted(
        float(listing["price"])
        for listing in comparables
        if listing.get("price") is not None
    )
    if not prices:
        return {
            "selected_price": selected_price,
            "average_price": None,
            "median_price": None,
            "comparable_count": 0,
            "verdict": "not enough data",
            "explanation": "There were no comparable listings available for a price check.",
        }

    average_price = round(sum(prices) / len(prices), 2)
    midpoint = len(prices) // 2
    if len(prices) % 2:
        median_price = prices[midpoint]
    else:
        median_price = round((prices[midpoint - 1] + prices[midpoint]) / 2, 2)

    category = item.get("category", "items")
    if selected_price <= median_price * 0.9:
        verdict = "good deal"
        explanation = (
            f"This ${selected_price:.2f} listing is below the ${median_price:.2f} "
            f"median for {len(prices)} comparable {category} listings."
        )
    elif selected_price >= median_price * 1.15:
        verdict = "pricey"
        explanation = (
            f"This ${selected_price:.2f} listing is above the ${median_price:.2f} "
            f"median for {len(prices)} comparable {category} listings."
        )
    else:
        verdict = "fair price"
        explanation = (
            f"This ${selected_price:.2f} listing is close to the ${median_price:.2f} "
            f"median for {len(prices)} comparable {category} listings."
        )

    return {
        "selected_price": selected_price,
        "average_price": average_price,
        "median_price": median_price,
        "comparable_count": len(prices),
        "verdict": verdict,
        "explanation": explanation,
    }


def load_style_profile() -> dict:
    """Load the local style profile memory, or return an empty profile."""
    try:
        with open(STYLE_PROFILE_PATH, "r", encoding="utf-8") as f:
            profile = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {key: value.copy() for key, value in DEFAULT_STYLE_PROFILE.items()}

    default_profile = {key: value.copy() for key, value in DEFAULT_STYLE_PROFILE.items()}
    for key in default_profile:
        if isinstance(profile.get(key), list):
            default_profile[key] = profile[key]
    return default_profile


def update_style_profile(query: str, selected_item: dict, wardrobe: dict | None = None) -> dict:
    """Update local style memory from the latest selected listing."""
    profile = load_style_profile()

    def prepend_unique(existing: list, new_values: list, limit: int) -> list:
        merged = []
        for value in new_values + existing:
            if value and value not in merged:
                merged.append(value)
        return merged[:limit]

    item_tags = selected_item.get("style_tags", []) if selected_item else []
    item_colors = selected_item.get("colors", []) if selected_item else []
    item_category = [selected_item.get("category")] if selected_item else []
    item_id = [selected_item.get("id")] if selected_item else []
    query_text = [query.strip()] if query and query.strip() else []

    profile["style_tags"] = prepend_unique(profile["style_tags"], item_tags, 12)
    profile["colors"] = prepend_unique(profile["colors"], item_colors, 12)
    profile["categories"] = prepend_unique(profile["categories"], item_category, 8)
    profile["recent_queries"] = prepend_unique(profile["recent_queries"], query_text, 8)
    profile["last_selected_item_ids"] = prepend_unique(profile["last_selected_item_ids"], item_id, 8)

    try:
        os.makedirs(os.path.dirname(STYLE_PROFILE_PATH), exist_ok=True)
        with open(STYLE_PROFILE_PATH, "w", encoding="utf-8") as f:
            json.dump(profile, f, indent=2)
    except OSError:
        pass

    return profile


# ── Tool 3: create_fit_card ───────────────────────────────────────────────────

def create_fit_card(outfit: str, new_item: dict) -> str:
    """
    Generate a short, shareable outfit caption for the thrifted find.

    Args:
        outfit:   The outfit suggestion string from suggest_outfit().
        new_item: The listing dict for the thrifted item.

    Returns:
        A 2–4 sentence string usable as an Instagram/TikTok caption.
        If outfit is empty or missing, return a descriptive error message
        string — do NOT raise an exception.

    The caption should:
    - Feel casual and authentic (like a real OOTD post, not a product description)
    - Mention the item name, price, and platform naturally (once each)
    - Capture the outfit vibe in specific terms
    - Sound different each time for different inputs (use higher LLM temperature)

    TODO:
        1. Guard against an empty or whitespace-only outfit string.
        2. Build a prompt that gives the LLM the item details and the outfit,
           and asks for a caption matching the style guidelines above.
        3. Call the LLM and return the response.

    Before writing code, fill in the Tool 3 section of planning.md.
    """
    if not outfit or not outfit.strip():
        return "Cannot create a fit card because the outfit suggestion is empty."

    if not new_item:
        return ""

    item_title = new_item.get("title", "this thrifted find")
    item_price = new_item.get("price", "unknown price")
    item_platform = new_item.get("platform", "unknown platform")

    prompt = (
        "Write a casual Instagram-style outfit caption in 1-3 sentences.\n"
        "It should sound like a real person sharing an outfit, not a product ad.\n"
        f"New item: {item_title}\n"
        f"Price: ${item_price}\n"
        f"Platform: {item_platform}\n"
        f"Outfit idea: {outfit}\n\n"
        "Naturally mention the item, price, platform, and overall outfit vibe."
    )

    try:
        client = _get_groq_client()
        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You write short, authentic outfit captions for social "
                        "posts. Avoid hashtags, bullet points, and product-copy tone."
                    ),
                },
                {"role": "user", "content": prompt},
            ],
            temperature=0.95,
            max_tokens=180,
        )
        return response.choices[0].message.content.strip()
    except Exception:
        return ""
