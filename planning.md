# FitFindr — planning.md

> Complete this document before writing any implementation code.
> Your spec and agent diagram are what you'll use to direct AI tools (Claude, Copilot, etc.) to generate your implementation — the more specific they are, the more useful the generated code will be.
> Your planning.md will be reviewed as part of your submission.
> Update it before starting any stretch features.

---

## Tools

List every tool your agent will use. For each tool, fill in all four fields.
You must have at least 3 tools. The three required tools are listed — add any additional tools below them.

### Tool 1: search_listings

**What it does:**
Searches the listings.json dataset for items matching the user's description, size, and price constraints. Filters all listings by the three parameters, sorts by relevance (matching description keywords and style_tags), and returns matching items. If no matches exist, returns an empty list.

**Input parameters:**
- `description` (str): keywords for the clothing item the user wants (e.g., "vintage graphic tee")
- `size` (str or None): desired size from 'XS' to 'XXXL', or None if size is flexible
- `max_price` (float): maximum acceptable price in dollars

**What it returns:**
- A list of matching listing dicts, each containing all 11 fields from listings.json: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `colors`, `brand`, `platform`. Sorted by relevance score (highest first). Returns up to 3 results; may return fewer if fewer matches exist. Returns an empty list `[]` if no matches found.

**What happens if it fails or returns nothing:**
- If results are empty, the agent logs the error in session["error"] and stops the workflow early. The user sees: "No matching listings were found for that description and price range. Try a different search."

---

### Tool 2: suggest_outfit

**What it does:**
Takes a single new item from search_listings and the user's wardrobe dict, then calls the LLM (Groq llama-3.3-70b-versatile) to generate 1–3 outfit suggestions that pair the new item with pieces from the wardrobe. The LLM reasons about color, style, and fit, returning complete outfit compositions. If the wardrobe is empty or minimal, the LLM still generates styling advice (e.g., "pair with basic jeans and a white tee").

**Input parameters:**
- `new_item` (dict): A single listing dict (with all 11 fields) that the user is considering buying
- `wardrobe` (dict): The user's wardrobe dict with schema: `{ 'items': [ {id, title, description, category, style_tags, size, condition, price, colors, brand, platform}, ... ] }`. May be empty.

**What it returns:**
- A string describing 1–3 outfit suggestions. Each suggestion includes: the new item, 2–4 pieces from the wardrobe (or styling guidance if wardrobe is empty), reasoning for why they work together, and optional accessories to elevate the look. Format example: "**Outfit 1:** Pair the faded band tee with your wide-leg jeans and platform Docs. Roll the sleeves once and tuck the front corner for shape. Add a vintage leather belt for definition."

**What happens if it fails or returns nothing:**
- If the LLM call fails or returns empty text, the agent logs an error and stores "suggest_outfit returned no valid outfit suggestions" in session["error"]. The agent then attempts to call search_listings again to find complementary pieces (e.g., searching for "jeans that match vintage band tee"). If this retry also fails or if max retries are reached (2 total search_listings attempts including the original), the agent stops and returns error to the user.

---

### Tool 3: create_fit_card

**What it does:**
Takes the outfit suggestion string from suggest_outfit and the new_item dict, then calls the LLM to write a short, shareable Instagram-style caption for the outfit. The caption should be authentic and capture the vibe of the styling — not a product description. It runs once per outfit suggestion (can generate multiple captions if multiple outfit suggestions were provided).

**Input parameters:**
- `outfit` (str): The outfit suggestion text from suggest_outfit (e.g., "Pair the faded band tee with your wide-leg jeans and platform Docs...")
- `new_item` (dict): The new listing dict (all 11 fields), so the caption can reference the source and price

**What it returns:**
- A string: a 1–3 sentence Instagram caption that includes the new item, its price/platform, and the vibe of the look. Example: "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"

**What happens if it fails or returns nothing:**
- If the LLM call fails or returns empty text, the agent logs an error: "create_fit_card returned no valid caption". The workflow stops and the user is shown: "We created outfit suggestions but couldn't generate a caption. Try again or adjust your query."

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**

The planning loop runs in the `run_agent(user_query, user_wardrobe)` function in agent.py and follows this conditional logic:

1. **Parse the query**: Extract description, size, and max_price from the user's plain-language query (using LLM or regex).

2. **Call search_listings**: Invoke `search_listings(description, size, max_price)`.
   - **If results are empty**: Set `session["error"]` to "No matching listings were found for that description and price range. Try a different search." and **return early** (workflow stops).
   - **If results are non-empty**: Store the top result in `session["selected_item"]` and proceed to step 3.

3. **Call suggest_outfit (first attempt)**: Invoke `suggest_outfit(session["selected_item"], user_wardrobe)`.
   - **If returned string is empty**: Store an error and proceed to step 4 (retry logic).
   - **If returned string is non-empty**: Store in `session["outfit_suggestion"]` and proceed to step 5.

4. **Retry with new search (optional)**: If suggest_outfit returned empty, attempt to call `search_listings` again with a modified query (e.g., remove size constraint, broaden price range) to find complementary pieces. This can happen **at most once** (one retry).
   - **If retry returns results**: Go back to step 3 with the new item.
   - **If retry also returns empty**: Set `session["error"]` to "Unable to build a complete outfit with your wardrobe and available listings. Try a different search." and **return early**.

5. **Call create_fit_card**: Invoke `create_fit_card(session["outfit_suggestion"], session["selected_item"])`.
   - **If returned caption is empty**: Set `session["error"]` to "We created outfit suggestions but couldn't generate a caption. Try again or adjust your query."
   - **If returned caption is non-empty**: Store in `session["fit_card"]` and **return the completed session**.

**End condition**: The agent always returns a session dict. If any branch hits an error, the session contains an error message and None values for unfilled fields. If the happy path completes, the session contains selected_item, outfit_suggestion, and fit_card.

---

## State Management

**How does information from one tool get passed to the next?**

The agent maintains a `session` dict that persists across all tool calls within a single user interaction. The session is initialized when `run_agent()` is called and returned to the user when the workflow completes (or errors out).

**Session dict structure:**
```python
session = {
    "user_query": str,           # Original user input (e.g., "I'm looking for a vintage graphic tee...")
    "selected_item": dict,       # The item dict returned by search_listings, with all 11 fields. None if search failed.
    "outfit_suggestion": str,    # Text from suggest_outfit describing how to style selected_item with wardrobe. None if suggest_outfit failed.
    "fit_card": str,             # Instagram caption from create_fit_card. None if create_fit_card failed.
    "error": str,                # Error message if any step failed. None if workflow succeeded.
    "retry_count": int           # Tracks how many times search_listings was retried (0 or 1).
}
```

**Data flow:**
1. `run_agent()` initializes session with all keys set to None except user_query and retry_count=0.
2. After `search_listings()` returns: session["selected_item"] is set to the first matching listing dict.
3. After `suggest_outfit()` returns: session["outfit_suggestion"] is set to the returned string.
4. If suggest_outfit fails and retry is triggered: retry_count is incremented, search_listings is called again with modified params, and session["selected_item"] is updated with the new item.
5. After `create_fit_card()` returns: session["fit_card"] is set to the returned caption string.
6. If any step errors: session["error"] is set and remaining fields stay None.

**Tool access pattern:**
- Tools are "dumb" — they do not read or write the session dict directly.
- The agent (planning loop) reads from the session to make decisions (e.g., "Is session['selected_item'] None? Then error.") and writes results into the session after each tool call.
- Tools are called as pure functions: `result = search_listings(desc, size, price)` then `session["selected_item"] = result[0]` inside the agent, not inside the tool.

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No listings match the query (returns empty list) | Agent sets session["error"] = "No matching listings were found for that description and price range. Try a different search." and returns early. Workflow stops. |
| search_listings (retry) | Retry also returns empty list after first attempt failed | Agent does not retry again. Sets session["error"] = "Unable to build a complete outfit with your wardrobe and available listings. Try a different search." and returns early. |
| suggest_outfit | LLM call fails or returns empty string | Agent logs error, then attempts one retry by calling search_listings again with loosened constraints (e.g., ignore size, increase max_price by 50%). If retry search returns results, try suggest_outfit again. If that also fails, set session["error"] = "Unable to build a complete outfit with your wardrobe and available listings. Try a different search." |
| suggest_outfit (empty wardrobe) | User's wardrobe has no items | Tool still generates styling advice (handled by LLM prompt: "If wardrobe is empty, provide general styling guidance"). This is NOT an error — workflow continues to create_fit_card. |
| create_fit_card | LLM call fails or returns empty string | Agent sets session["error"] = "We created outfit suggestions but couldn't generate a caption. Try again or adjust your query." and returns early. |

---

## Architecture

---
config:
  layout: elk
---
flowchart TB
    A["User Query"] --> B["Extract Info & Create Input Variables"]
    B --> C{"search_listings Iterations < 4?"}
    C -- No --> E["Return Standard Error Message"]
    C -- Yes --> D["Call search_listings Tool"]
    D --> F{"search_listings Output Valid?"}
    F -- Empty/Error --> E
    F -- Valid --> G["Structure Output to Dict"]
    G --> H{"suggest_outfit Iterations < 4?"}
    H -- No --> E
    H -- Yes --> I["Call suggest_outfit with Top 1-3 Listings"]
    I --> J{"suggest_outfit Output Valid?"}
    J -- Empty --> C
    J -- Valid --> K["Output Outfits Dict"]
    K --> L["Call create_fit_card Tool"]
    L --> M{"Output Valid?"}
    M -- Invalid --> N["Call try-assert Debugging"]
    N --> O{"Assertions Pass?"}
    O -- No --> E
    O -- Yes --> P["Return Corrected Output"]
    M -- Valid --> P
    P --> Q["Generate 3 Fit Card Tables"]
    Q --> R["Sort by Matching Score"]
    R --> S["Display Tables with Components"]
    S --> T["Show Need to Get/Purchase Items"]
    T --> U["Show Already Owned Items"]
    U --> V["Return to User"]

    style A fill:#eef2ff,stroke:#818cf8
    style B fill:#eef2ff,stroke:#818cf8
    style C fill:#fef2f2,stroke:#f87171
    style D fill:#f0fdfa,stroke:#2dd4bf
    style F fill:#f0fdfa,stroke:#2dd4bf
    style G fill:#f0fdfa,stroke:#2dd4bf
    style H fill:#fef2f2,stroke:#f87171
    style I fill:#f0fdf4,stroke:#4ade80
    style J fill:#f0fdf4,stroke:#4ade80
    style K fill:#f0fdf4,stroke:#4ade80
    style L fill:#ecfeff,stroke:#22d3ee
    style N fill:#f5f3ff,stroke:#a78bfa
    style P fill:#ecfeff,stroke:#22d3ee
    style Q fill:#ecfeff,stroke:#22d3ee
    style V fill:#ecfeff,stroke:#22d3ee

**Key flow points:**
- All decisions (branches, retries, tool calls) happen in the `run_agent()` planning loop in agent.py
- Tools are pure functions: they receive input params, return output, and do not touch the session dict
- The agent reads tool outputs and writes them to the session before deciding what to call next
- Error paths return early with a populated session["error"] and None values for incomplete fields

---

## AI Tool Plan

**Milestone 3 — search_listings implementation:**
I'll give Claude the "Tool 1: search_listings" section from planning.md (inputs, return value, failure mode). I'll ask it to implement the function using `load_listings()` from utils/data_loader.py. Before running it, I'll verify the generated code filters by all three parameters (description, size, max_price), returns a list of dicts (not strings), handles empty results by returning `[]`, and sorts by relevance. Then I'll test with:
- Query: "vintage graphic tee", size=None, max_price=50 → expect results list with price ≤ 50
- Query: "designer ballgown", size="XXS", max_price=5 → expect empty list `[]`
- Query: "jacket" with no size filter → expect results including all sizes

**Milestone 3 — suggest_outfit implementation:**
I'll give Claude the "Tool 2: suggest_outfit" section, specifying that it should use Groq's llama-3.3-70b-versatile with the GROQ_API_KEY from .env. I'll ask it to craft a system prompt that tells the LLM to generate outfit suggestions pairing the new item with wardrobe pieces, and to provide general styling advice if wardrobe is empty. Before running it, I'll verify the returned string is non-empty even for empty wardrobe, contains styling suggestions, and mentions the new item. I'll test with:
- A band tee + full wardrobe → expect outfit with specific pieces from wardrobe
- Same band tee + empty wardrobe → expect general styling advice (no crash)
- Run 3 times on same input → expect different suggestions (LLM temperature is > 0)

**Milestone 3 — create_fit_card implementation:**
I'll give Claude the "Tool 3: create_fit_card" section and ask it to call the LLM with a prompt that generates short Instagram captions (1–3 sentences). Before running it, I'll verify the returned caption is a string, references the item and price/platform, and sounds like a social media post (not a product description). I'll test with:
- A band tee + its outfit suggestion → expect caption mentioning the tee, price, and vibe
- Run 3 times on same input → expect different captions
- Empty outfit string → expect error message string (no crash)

**Milestone 4 — Planning loop implementation:**
I'll give Claude the entire "Planning Loop" section, the "State Management" section, and the Architecture diagram. I'll ask it to implement `run_agent()` in agent.py following the numbered steps in the TODO. Before running it, I'll verify:
- After search_listings returns empty, no other tools are called and session["error"] is set
- After search_listings returns results, session["selected_item"] is the first result (a dict, not a string)
- After suggest_outfit returns text, session["outfit_suggestion"] contains that text
- The retry logic only happens once (retry_count ≤ 1)
- All branches eventually return a session dict

**Milestone 4 — Gradio integration:**
I'll give Claude the "State Management" section and ask it to implement `handle_query()` in app.py. The function should call `run_agent(query, wardrobe)` and map session["selected_item"], session["outfit_suggestion"], and session["fit_card"] to the three output panels. If session["error"] is set, display the error in the first panel instead.
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Parse & Setup:**
- run_agent() is called with the user query and their wardrobe dict (e.g., `{ 'items': [jeans_dict, sneakers_dict, ...] }`)
- session is initialized with all fields = None, retry_count = 0
- Agent extracts: description="vintage graphic tee", size=None, max_price=30.0

**Step 1 — search_listings:**
- Agent calls: `search_listings("vintage graphic tee", size=None, max_price=30.0)`
- Tool searches listings.json, filters by price ≤ $30 and description match, sorts by relevance (matching "graphic tee" and "vintage")
- Returns: `[{id: "dep_001", title: "Faded Band Tee", price: 22.0, size: "M", platform: "Depop", ...}, {id: "dep_002", ...}, ...]`
- Agent stores: `session["selected_item"] = results[0]` (the Faded Band Tee)
- ✅ Proceed to Step 2

**Step 2 — suggest_outfit:**
- Agent calls: `suggest_outfit(session["selected_item"], user_wardrobe)`
- Tool sends to LLM: "Given this faded band tee and the user's wardrobe (baggy jeans, chunky sneakers, ...), suggest a complete outfit."
- LLM returns: "Pair this faded band tee with your wide-leg jeans and platform Docs for a classic 90s grunge look. Roll the sleeves once and tuck the front corner slightly for shape."
- Agent stores: `session["outfit_suggestion"] = <that string>`
- ✅ Proceed to Step 3

**Step 3 — create_fit_card:**
- Agent calls: `create_fit_card(session["outfit_suggestion"], session["selected_item"])`
- Tool sends to LLM: "Write a short Instagram caption for this outfit: [outfit text]. The new item is a Faded Band Tee from Depop for $22."
- LLM returns: "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"
- Agent stores: `session["fit_card"] = <that caption>`
- ✅ Workflow complete

**Return to user:**
- session["fit_card"] displays in the third panel: "thrifted this faded band tee off depop for $22 and honestly it was made for my wide-legs 🖤 full look in my stories"
- session["outfit_suggestion"] displays in the second panel: outfit pairing advice
- session["selected_item"]["title"] and other details display in the first panel

**Error path example:**
If search_listings returned empty (no vintage tees under $30), the agent would:
1. Set `session["error"] = "No matching listings were found for that description and price range. Try a different search."`
2. Return early without calling suggest_outfit or create_fit_card
3. User sees the error message in the first output panel; other panels remain empty
