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
search_listings() will take the user's query, pre-converted into exact keywords (e.g. 'vintage graphic tee', 'under $30', 'M') and context keywords (e.g. 'pairs well with baggy jeans and chunky sneakers'), and finds listings directly matching user preferences and sorting by relevance based on the their matching score with the context keywords and returning the top 3.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `description` (str): the exact clothing article the user wants
- `size` (str): listed in sizes from 'XS-XXXL'
- `max_price` (float): dollar amount capped to two decimal places

**What it returns:**
<!-- Describe the return value — what fields does a result contain? -->
- Three strings in the format: "{optional: brand}:{product name}: {price},{size},{platform}"

**What happens if it fails or returns nothing:**
- Output: "No matching listings were found. Please try a different query."

---

### Tool 2: suggest_outfit

**What it does:**
Read the output (str->dict) from search_listings and user's wardrobe (dict) and formulates outfit ideas using each of the top 3 listings to create the best-matching outfits that captures the user's query. If none are available, it will create a new query for the search_listing function to find matching pieces for each of the 3 listings.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `new_item` (dict): top 3 listings with all 11 properties retrieved from listings.json
- `wardrobe` (dict): the user's pre-filled wardrobe with all listings with fields for all 11 properties (marked as None or N/A as appropriate if user doesn't provide sufficient info)

**What it returns:**
<!-- Describe the return value -->
If matches are found, it will return matching pieces to complete the outfit from the wardrobe as well as the info for the new item(s). `outfits` (dict)

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the wardrobe is empty or no outfit can be suggested? -->
Otherwise, it will feed search_listings query to find matching pieces from listings to go with the original suggestions (top 3). It will count iterations of how many times it has been called and immediately exits loop if iteration number is greater than 3, returning "Max iterations reached. No outfits are possible with the given parameters." Agent will read this and provide the user the standard error message as output. Output: "No matching listings were found. Please try a different query."

---

### Tool 3: create_fit_card

**What it does:**
If valid matches are returned from the suggest_outfit, the outfit listings will be built back into plain speech for the user to build easily (return each outfit as a table) and provide new items at the top with their platform and price at the front followed by the user's already owned items (from wardrobe). Make sure to find some extra optional accessories and add to each outfit table (including price and platform only) and clearly mark as optional for the user.

**Input parameters:**
<!-- List each parameter, its type, and what it represents -->
- `outfit` (dict): Up to 3 outfits including all relevant listing info for new fits and wardrobe options paired together into up to three dicts

**What it returns:**
- `user outfit` (table): Creates a table for each outfit and return all components of the outfit (adding a category for whether its already in the wardrobe or needs to be sourced) - has to make sure all non-wardrobe items are labelled as such for user convenience

**What happens if it fails or returns nothing:**
<!-- What should the agent do if the outfit data is incomplete? -->
If the tool doesn't receive any input, exit the loop immediately and print the standard error message Output: "No matching listings were found. Please try a different query." Otherwise, use a helper function to check each cell of the outfit components identifiers and rewrite any errors to 'N/A' then see try-assert to see if the expected output is returnable and return. If this helper function doesn't work, return the standard error message Output: "No matching listings were found. Please try a different query."

---

### Additional Tools (if any)

<!-- Copy the block above for any tools beyond the required three -->

---

## Planning Loop

**How does your agent decide which tool to call next?**
<!-- Describe the logic your planning loop uses. What does it look at? What conditions change its behavior? How does it know when it's done? -->
The user query must be extracted for info and appropriately converted into input variables structured for the search_listings tool. If output of the search_listings tool is empty or erroneous, return the standard error message: "No matching listings were found. Please try a different query." If successful, output of the search_listings must be structured into the appropriate dict data structure and given to the suggest_outfit function for the 1-3 top listing strings.

If the suggest_outfit function returns an empty output, restructure the listings to input back into the search_listings function, looking for matching pieces to fit this clothing with the user query as context; count the iterations in the search_listings tool and output "Max iterations reached" to the agent if iteration number is 4 (where search_listings or suggest_outfit is called more than 3 times). If the agent encounters this from either tool, DO NOT feed back into that same tool. Continue workflow until both tools reach max iterations and return standard error message.

If the suggest_outfit function lists up to 3 valid outfits, return outfits (dict) which the agent should check if they are properly structured and feed directly into the create_fit_card tool. If output is empty return standard error message. If the tool is not valid, attempt the try-assert debugging tool implemented in the helper function as described in the Tool 3 planning loop then return error message if unsuccessful or invalid assertions are given. If successful, user should see 3 fit cards in tabular form where each outfit table shows the list of components in listing format and an extra cell included for all the pieces retrieved from listings.json (marked as need to get/purchase) followed by all the pieces from user's wardrobe (marked as already owned). The outfit tables (up to 3) must be in order of best matching score to user query to worst matching score.

---

## State Management

**How does information from one tool get passed to the next?**
<!-- Describe how your agent stores and accesses state within a session. What data is tracked? How is it passed between tool calls? -->

---

## Error Handling

For each tool, describe the specific failure mode you're handling and what the agent does in response.

| Tool | Failure mode | Agent response |
|------|-------------|----------------|
| search_listings | No results match the query | "No matching listings were found. Please try a different query." |
| suggest_outfit | Wardrobe is empty | "Please enter at least 5 items in your wardrobe. 10-20 listings are recommended in your wardrobe for a stylist fit."|
| create_fit_card | Outfit input is missing or incomplete | Run the helper function to try debugging and if assertions arise, output standard error message: "No matching listings were found. Please try a different query."|

---

## Architecture

<!-- Draw a diagram of your agent showing how the components connect:
     User input → Planning Loop → Tools (search_listings, suggest_outfit, create_fit_card)
                                                                          ↕
                                                                   State / Session
     Show what triggers each tool, how state flows between them, and where error paths branch off.
     ASCII art, a Mermaid diagram (https://mermaid.js.org/syntax/flowchart.html), or an embedded
     sketch are all fine. You'll share this diagram with an AI tool when asking it to implement
     the planning loop and each individual tool. -->

---

## AI Tool Plan

<!-- For each part of the implementation below, describe:
     - Which AI tool you plan to use (Claude, Copilot, ChatGPT, etc.)
     - What you'll give it as input (which sections of this planning.md, your agent diagram)
     - What you expect it to produce
     - How you'll verify the output matches your spec before moving on

     "I'll use AI to help me code" is not a plan.
     "I'll give Claude my Tool 1 spec (inputs, return value, failure mode) and ask it to implement
     search_listings() using load_listings() from the data loader — then test it against 3 queries
     before trusting it" is a plan. -->

**Milestone 3 — Individual tool implementations:**
I'm using Claude to implement the tool call implementations, feeding it the entire planning.md for context then telling it to implement each tool block that I feed it. I'll tell it to implement it using load_listings() from the data loader utility. Then I'll ask the AI to run empty and edge cases as well as provide it 3 queries to run and check if the tool works in isolation.

**Milestone 4 — Planning loop and state management:**
Then depending on credits, I'll switch to Codex or stay here to implement the agent and wire it up to the tools and LLM. I'll ask for suggestions on my state management based on my planning loop and append it to be clear for the AI. Then feed it my agent diagram and planning loop/state management sections to agent.py. Use it to debug any problems I might face on the rest of the TODO list
---

## A Complete Interaction (Step by Step)

Write out what a full user interaction looks like from start to finish — tool call by tool call. Use a specific example query.

**Example user query:** "I'm looking for a vintage graphic tee under $30. I mostly wear baggy jeans and chunky sneakers. What's out there and how would I style it?"

**Step 1:**
The user's plain speech query will trigger the search_listings agent to find listings relevant to "vintage graphic tee", price under $30, checking for listings that pair well with baggy jeans and chunky sneakers and returns the top 3 suitable pieces if available. If not, it will return empty and this will be output to the user as "No matching listings were found. Please try a different query."

**Step 2:**
If empty output from search_listings was detected, the error message above will be sent to the user and it will exit the loop early. Else the sorted output from search_listings will be fed to the suggest_outfit agent which will analyze which of the selected pieces best fit the user's query under the context of suitable matching pieces from the user's pre-entered wardrobe to build a new fit best fitting for the query, returning the top 3 fully-built options. It will return this as a json to the create_fit_card agent. If no suitable pieces were found in the user's wardrobe, it will return the best sorted list of pieces back into the search_listings to find matching pieces to both fit the user's query and match with the given listings.

**Step 3:**
It will reiterate through the search_listings and suggest_outfit agents till top 3 outfit suggestions are built and returned to the create_fit_card. After 3 iterations of either agent without a full outfit, verified and thrown back to the suggest_outfit agent by the create_fit_card agent, it will output to the user the same standard error message: "No matching listings were found. Please try a different query." Each agent will keep track of their own iterations till query is satisfied, outputting this message after the third iteration if create_fit_card is dissatisfied.

**Final output to user:**
If it contains sufficient info, checking if it includes all pieces needed for a full outfit, it will create a readable table of clothing to put together, including optional accessories and add-ons suggested to fulfill the user's query.
