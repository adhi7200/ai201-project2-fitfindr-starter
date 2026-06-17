# FitFindr

FitFindr is a multi-tool AI agent for secondhand fashion shopping. A user describes what they want in natural language, the agent searches mock thrift listings, checks the price, brings in saved style preferences and trend context, styles one matching item with the user's wardrobe, and turns the outfit into a short shareable fit card.

The project uses:
- Mock listing data from `data/listings.json`
- Wardrobe examples from `data/wardrobe_schema.json`
- Local style memory in ignored file `data/style_profile_memory.json`
- A curated offline trend map in `tools.py`
- Groq `llama-3.3-70b-versatile` for outfit and caption generation
- Gradio for the local demo UI

## Setup

```bash
pip install -r requirements.txt
```

Create a `.env` file in the project root:

```bash
GROQ_API_KEY=your_key_here
```

Run the app:

```bash
python app.py
```

Run tests:

```bash
python -m pytest tests/
```

## Tool Inventory

### `search_listings(description, size, max_price)`

Purpose: searches `data/listings.json` for secondhand listings that match the user's request.

Inputs:
- `description` (`str`): item keywords, such as `"vintage graphic tee"` or `"90s track jacket"`.
- `size` (`str | None`): optional size filter, such as `"M"`, `"S/M"`, `"W30"`, or `"US 8"`.
- `max_price` (`float | None`): optional maximum price in dollars.

Returns:
- `list[dict]`: up to 3 listing dictionaries sorted by relevance.
- Each listing contains `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, and `platform`.
- Returns `[]` when no listing matches.

### `compare_price(item)`

Purpose: estimates whether the selected listing is a good deal, fair price, pricey, or has too little data.

Inputs:
- `item` (`dict`): the selected listing from `search_listings`.

Returns:
- `dict` with `selected_price`, `average_price`, `median_price`, `comparable_count`, `verdict`, and `explanation`.

How comparisons are made: the tool first looks for listings in the same category, then prefers comparable listings with overlapping style tags or colors. If that narrowed set is empty, it falls back to same-category listings. It compares the selected price to the comparable median: at or below 90% is a good deal, at or above 115% is pricey, and the middle range is fair.

### `check_trends(description, size, item)`

Purpose: returns trend context that can influence the outfit suggestion.

Inputs:
- `description` (`str`): parsed item keywords.
- `size` (`str | None`): optional parsed size.
- `item` (`dict | None`): selected listing from `search_listings`.

Returns:
- `dict` with `matched_trends`, `trend_tags`, `confidence`, `matched_keywords`, `style_note`, and `source`.

Data source: the trend tool uses a curated local trend map in `tools.py`, based on common public resale and fashion trend reporting categories such as Y2K nostalgia, neo-grunge, sporty vintage, soft utility, romantic vintage, and modern prep. It is offline on purpose so the demo is stable and does not depend on scraping a live platform.

### `load_style_profile()` and `update_style_profile(query, selected_item, wardrobe)`

Purpose: remembers lightweight user preferences across runs.

Inputs:
- `query` (`str`): the user's natural language request.
- `selected_item` (`dict`): the listing chosen by the agent.
- `wardrobe` (`dict`): the active wardrobe dictionary.

Returns:
- `dict` with remembered `style_tags`, `colors`, `categories`, `recent_queries`, and `last_selected_item_ids`.

Storage approach: memory is stored locally in `data/style_profile_memory.json`, which is ignored by git. The agent loads it at the start of each interaction, updates it after selecting a listing, and passes it into `suggest_outfit` as extra wardrobe context. In a two-interaction demo, the first query writes preferences like `vintage`, `grunge`, and `black`; the second query can use those preferences without the user re-entering them.

### `suggest_outfit(new_item, wardrobe)`

Purpose: uses the selected listing, wardrobe, style memory, and trend awareness to generate outfit suggestions.

Inputs:
- `new_item` (`dict`): one listing dictionary returned by `search_listings`.
- `wardrobe` (`dict`): wardrobe data with an `items` list. The agent may also add `_style_profile` and `_trend_awareness` context before calling this tool.

Returns:
- `str`: 1-2 outfit suggestions.
- With an example wardrobe, the response names specific owned pieces and explains why they work.
- With an empty wardrobe, the response gives general styling advice using common basics.
- Returns `""` if the LLM call fails.

### `create_fit_card(outfit, new_item)`

Purpose: turns the outfit suggestion into a short shareable caption.

Inputs:
- `outfit` (`str`): outfit text returned by `suggest_outfit`.
- `new_item` (`dict`): the selected listing dictionary.

Returns:
- `str`: a 1-3 sentence caption that mentions the item, price, platform, and outfit vibe.
- If `outfit` is empty, returns `"Cannot create a fit card because the outfit suggestion is empty."`
- Returns `""` if the LLM call fails.

## Planning Loop

The planning loop lives in `run_agent(query, wardrobe)` in `agent.py`. It checks state after each step and only calls tools whose required inputs exist.

1. Initialize `session` with the query, wardrobe, empty output fields, `retry_count = 0`, and loaded style memory.
2. Parse the query into `description`, `size`, and `max_price`.
3. Call `search_listings(description, size, max_price)`.
4. If search returns `[]`, retry without the size filter when size was provided. If still empty, retry without the price ceiling when price was provided. Store each adjustment in `session["search_fallbacks"]`.
5. If every search attempt fails, set a no-results error and stop before calling later tools.
6. Store the top listing as `session["selected_item"]`.
7. Call `compare_price(selected_item)` and store `session["price_comparison"]`.
8. Call `check_trends(description, size, selected_item)` and store `session["trend_awareness"]`.
9. Call `update_style_profile(query, selected_item, wardrobe)` and store `session["style_profile"]`.
10. Call `suggest_outfit(selected_item, wardrobe_with_memory_and_trends)`.
11. If outfit generation fails, retry once with another listing from `session["search_results"]`. The agent refreshes price, trend, and memory state for the alternate item before trying again.
12. If outfit generation succeeds, call `create_fit_card(outfit_suggestion, selected_item)`.

This means the agent behaves differently for non-standard input. A happy path uses all tools. A zero-result query first loosens search constraints and explains what changed. A failed outfit attempt retries with a different matched item instead of asking the user to re-enter anything.

## State Management

State is passed through one `session` dict inside `run_agent()`:

```python
{
    "query": str,
    "parsed": {"description": str, "size": str | None, "max_price": float | None},
    "search_results": list[dict],
    "selected_item": dict | None,
    "wardrobe": dict,
    "search_fallbacks": list[str],
    "price_comparison": dict | None,
    "trend_awareness": dict | None,
    "style_profile": dict,
    "style_profile_note": str | None,
    "outfit_suggestion": str | None,
    "fit_card": str | None,
    "retry_count": int,
    "error": str | None,
}
```

The same listing dict returned by `search_listings` is stored as `selected_item`, passed into `compare_price`, passed into `check_trends`, passed into `suggest_outfit`, and finally passed into `create_fit_card`. The outfit string from `suggest_outfit` is stored as `outfit_suggestion` and passed directly into `create_fit_card`. The user never has to re-enter the selected item or outfit.

## Error Handling

| Tool | Failure mode | Agent behavior |
|------|--------------|----------------|
| `search_listings` | No listings match. | Retry without size, then without price if available. Show the adjustment notes. If still empty, stop with a no-results error. |
| `compare_price` | No comparable listings exist. | Return `verdict = "not enough data"` and continue. |
| `check_trends` | No trend keywords match. | Return `confidence = "low"` with a generic item-based style note and continue. |
| `load_style_profile` / `update_style_profile` | Memory file is missing, unreadable, or cannot be written. | Use an empty/default profile and continue. |
| `suggest_outfit` | LLM call fails or returns empty text. | Retry once with another matched listing. If the retry fails, stop with an outfit error. |
| `create_fit_card` | LLM call fails or receives an empty outfit. | Stop with a caption error. |

Concrete tested examples:
- `search_listings("designer ballgown", size="XXS", max_price=5)` returns `[]`.
- `run_agent("designer ballgown size XXS under $5", wardrobe)` records both fallback adjustments before returning the no-results error.
- `compare_price(item)` returns a verdict and reasoning using comparable listing prices.
- `check_trends("vintage graphic tee", None, item)` returns `"Neo-grunge"` trend context.
- `update_style_profile(...)` writes selected item preferences to a local JSON memory file.
- `suggest_outfit(...)` includes both style memory and trend awareness in the LLM prompt during tests.
- `create_fit_card("", item)` returns the explicit empty-outfit error string.

## Example Interaction

User query:

```text
I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers.
```

Agent flow:
1. `run_agent()` parses `description="vintage graphic tee"`, `size=None`, and `max_price=30.0`.
2. `search_listings("vintage graphic tee", None, 30.0)` returns matching listings such as `lst_033` or `lst_006`.
3. The top listing is stored as `session["selected_item"]`.
4. `compare_price(session["selected_item"])` returns a price verdict with comparable median/average reasoning.
5. `check_trends("vintage graphic tee", None, session["selected_item"])` returns trend context such as `"Neo-grunge"`.
6. `update_style_profile(...)` stores the selected item's style tags, colors, category, query, and id.
7. `suggest_outfit(session["selected_item"], wardrobe_with_memory_and_trends)` styles that same listing with wardrobe pieces and the trend note.
8. `create_fit_card(session["outfit_suggestion"], session["selected_item"])` creates the final caption.
9. Gradio displays the selected listing with price check, the outfit idea with memory/trend notes, and the fit card.

Second interaction memory example:
1. First query: `"vintage graphic tee under $30"` selects a grunge/streetwear tee and stores those preferences.
2. Second query: `"black boots size 8"` does not restate grunge or streetwear.
3. The agent loads `data/style_profile_memory.json`, passes the remembered style tags into `suggest_outfit`, and displays a `"Style memory used"` note in the outfit panel.

Fallback example:
1. Query: `"designer ballgown size XXS under $5"`.
2. Initial search returns no results.
3. The agent retries without `size="XXS"`.
4. If still empty, it retries without the `$5` price ceiling.
5. If still empty, the first Gradio panel explains that no matching listings were found and the workflow stops before outfit or caption generation.

## Testing

The tests in `tests/` verify:
- Search matching, empty results, and price filtering.
- Price comparison verdicts and no-comparable fallback.
- Trend matching and low-confidence fallback.
- Style profile loading, updating, and prompt injection.
- Outfit generation with empty and example wardrobes.
- Trend awareness prompt injection.
- Fit card generation and empty outfit handling.
- Agent-level search fallback, style memory, trend state, and retry behavior.

LLM-dependent tests use mocks, so the test suite is fast and does not require live API calls.

## Spec Reflection

One way the spec helped: defining each tool's inputs and return values before implementation made the state flow straightforward. `search_listings` returns listing dicts, `suggest_outfit` receives one of those dicts, and `create_fit_card` receives the outfit string plus the same selected item.

One implementation divergence: the original starter spec did not include `retry_count`, but the final plan added it to make the one allowed `suggest_outfit` retry explicit and testable. This keeps the adaptive loop simple while still showing behavior that changes based on tool output.

## AI Usage

I used AI assistance in two main ways:

1. **Planning and spec cleanup:** I used AI to clean up and give a sanity check on my project instructions to ensure there weren't any contradictions and that the logic remains consistent and in line with the project expectations given the rubric and the `planning.md` spec. I manually added the given suggestions to ensure my plan wasn't being altered.
2. **Implementation support:** I used the Tool Inventory, Planning Loop, State Management, and Error Handling sections from `planning.md` to guide implementation of the three tools, `run_agent()`, and `handle_query()`. I verified the generated logic against the spec by running tool tests, direct agent checks, and Gradio handler checks.
3. **Polishing and Wrapping up README:*** Similar to the planning support, I used AI to ensure my `README.md` captured all areas of the project and iteratively used it to make sure all sections fully meet rubric expectations. I went back to read the `README.md` to make sure it is consistent with the project and `planning.md`.

I overrode or tightened AI output to reflect project requirements and my spec where needed, especially around query parsing and retry behavior. For example, the agent only retries `suggest_outfit` after a successful search, and it uses another matched listing rather than broadening the original search.