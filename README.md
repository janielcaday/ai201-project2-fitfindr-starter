# FitFindr — Starter Kit

This starter kit contains everything you need to begin Project 2.

## What's Included

```
ai201-project2-fitfindr-starter/
├── data/
│   ├── listings.json          # 40 mock secondhand listings
│   └── wardrobe_schema.json   # Wardrobe format + example wardrobe
├── utils/
│   └── data_loader.py         # Helper functions for loading the data
├── planning.md                # Your planning template — fill this out first
└── requirements.txt           # Python dependencies
```

## Setup

```bash
pip install -r requirements.txt
```

Set your Groq API key in a `.env` file (get a free key at [console.groq.com](https://console.groq.com)):
```
GROQ_API_KEY=your_key_here
```

## The Mock Listings Dataset

`data/listings.json` contains 40 mock secondhand listings across categories (tops, bottoms, outerwear, shoes, accessories) and styles (vintage, y2k, grunge, cottagecore, streetwear, and more).

Each listing has: `id`, `title`, `description`, `category`, `style_tags`, `size`, `condition`, `price`, `brand`, and `platform`.

Load it with:
```python
from utils.data_loader import load_listings
listings = load_listings()
```

## The Wardrobe Schema

`data/wardrobe_schema.json` defines the format your agent uses to represent a user's existing wardrobe. It includes:

- `schema`: field definitions for a wardrobe item
- `example_wardrobe`: a sample wardrobe with 10 items you can use for testing
- `empty_wardrobe`: a starting template for a new user

Load an example wardrobe with:
```python
from utils.data_loader import get_example_wardrobe
wardrobe = get_example_wardrobe()
```

## Where to Start

1. **Read `planning.md` and fill it out before writing any code.**
2. Verify the data loads correctly by running `python utils/data_loader.py`.
3. Build and test each tool individually before connecting them through your planning loop.

Your implementation files go in this same directory. There's no required file structure for your agent code — organize it however makes sense for your design.

# Tool Inventory

## Tool 1:
### Name: search_listings
### Inputs:
**Parameter Names & Types:**
- `description` (str): keywords describing what the user is looking for (e.g. `"vintage graphic tee"`)
- `size` (str | None): size string to filter by, case-insensitive (e.g. `"M"` matches `"S/M"`); `None` skips size filtering
- `max_price` (float | None): maximum price, inclusive; `None` skips price filtering

### Outputs:
list[dict] — matching listing dicts sorted by relevance score (best match first). Each dict contains: `id`, `title`, `description`, `category`, `style_tags` (list[str]), `size`, `condition`, `price` (float), `colors` (list[str]), `brand`, `platform`. Returns an empty list if nothing matches.

### Purpose:
Searches the mock listings dataset for secondhand items matching the user's description keywords, with optional size and price filters. Scores each listing by keyword overlap and drops zero-score results.


## Tool 2:
### Name: suggest_outfit
### Inputs:
**Parameter Names & Types:**
- `new_item` (dict): a listing dict for the item the user is considering buying
- `wardrobe` (dict): wardrobe dict with an `'items'` key containing a list of wardrobe item dicts; may be empty

### Outputs:
str — a non-empty string with 1–2 complete outfit suggestions pairing the new item with named pieces from the wardrobe. If the wardrobe is empty, returns general styling advice (what pairs well, what vibe the item suits, 1–2 example outfits using common staples) instead of raising an exception or returning an empty string.

### Purpose:
Given a thrifted item and the user's existing wardrobe, calls the LLM (Groq / llama-3.3-70b-versatile) to suggest complete outfit combinations or provide general styling guidance when no wardrobe is available.

## Tool 3:
### Name: create_fit_card
### Inputs:
**Parameter Names & Types:**
- `outfit` (str): the outfit suggestion string returned by `suggest_outfit()`
- `new_item` (dict): the listing dict for the thrifted item (used for caption details and fallback advice)

### Outputs:
str — a 2–4 sentence Instagram/TikTok OOTD caption that mentions the item name, price, and platform naturally, each exactly once. If `outfit` is empty or whitespace-only, returns a descriptive fallback string using the item's category, colors, and style tags — does NOT raise an exception or call the LLM.

### Purpose:
Generates a casual, shareable outfit caption for the thrifted find using the LLM at high temperature (1.0) for creative variation across runs.

# Planning Loop Explanation

The loop runs these steps in order and stops early on any failure — it never calls all three tools unconditionally:

1. **Parse query** — regex extracts `size` (pattern: `size [A-Z]+`, case-insensitive) and `max_price` (pattern: `under $N`) from the raw query string; remaining text becomes `description`.
2. **Search** — calls `search_listings(description, size, max_price)`. If the result list is empty, sets `session["error"]` to a message naming the unmatched description and filters (e.g. size, price), then returns immediately — `suggest_outfit` is never called with empty input.
3. **Select** — stores `results[0]` (highest-relevance listing) in `session["selected_item"]`.
4. **Suggest outfit** — calls `suggest_outfit(selected_item, wardrobe)`. If the returned string is empty or whitespace-only, sets `session["error"]` and returns early without calling `create_fit_card`.
5. **Create fit card** — calls `create_fit_card(outfit_suggestion, selected_item)` and stores the caption in `session["fit_card"]`.
6. **Return** — returns the completed session dict; caller checks `session["error"]` first.

# State Management Approach

All state lives in a single `session` dict initialized by `_new_session()` in `agent.py`. No data is re-entered by the user between steps — each tool's output is stored in the session and read directly by the next tool call.

| Field | Written by | Read by |
|-------|-----------|---------|
| `parsed` | query parser (Step 2) | `search_listings` call |
| `search_results` | `search_listings` (Step 3) | Step 4 selection |
| `selected_item` | Step 4 (top of `search_results`) | `suggest_outfit`, `create_fit_card` |
| `outfit_suggestion` | `suggest_outfit` (Step 5) | `create_fit_card` |
| `fit_card` | `create_fit_card` (Step 6) | Gradio UI output panel |
| `error` | any early-exit step | caller / UI layer |

`selected_item` flows directly from `search_listings` output into `suggest_outfit` as `new_item`. `outfit_suggestion` flows directly from `suggest_outfit` output into `create_fit_card` as `outfit`. The Gradio UI in `app.py` reads `session["selected_item"]`, `session["outfit_suggestion"]`, and `session["fit_card"]` to populate its three output panels.

# Error Handling Per Tool
| Tool | Failure mode | Expected Agent Response | Actual Agent Response |
|------|--------------|-------------------------|-----------------------|
| `search_listings` | No listings match the description/size/price filters | Sets `session["error"]` with a message naming the failed filters and advises broadening the search; returns early — `suggest_outfit` is never called | No listings found matching 'designer ballgown  under', size XXS. Try broadening your search. |
| `suggest_outfit` | Wardrobe is empty (`wardrobe['items']` is `[]`) | Calls LLM with a general-styling prompt instead of outfit-matching prompt; returns non-empty string with styling advice — does not raise or return empty | Congratulations on finding a great thrifted item. The Vintage Levi's 501 Jeans are a classic and versatile piece that can be styled in many ways. Here are some general styling advice and outfit ideas to get you started: Pairs well with: The medium wash and classic style of these jeans make them a great foundation for a variety of outfits. They pair well with: Plain white or black tops, such as t-shirts, tank tops, or sweaters, Leather jackets or denim jackets for a cool, layered look, Sneakers, boots, or loafers for a casual, streetwear-inspired vibe, Flannel shirts or button-downs for a more rustic, laid-back look. Vibe or aesthetic: These jeans suit a laid-back, casual aesthetic with a hint of vintage charm. They're perfect for a streetwear-inspired look, a relaxed weekend outfit, or a casual everyday style. Example outfit ideas: 1. Classic Casual: Pair the Vintage Levi's 501 Jeans with a plain white t-shirt, a black leather jacket, and a pair of white sneakers. This outfit is simple, yet stylish and perfect for a casual day out. 2. Weekend Brunch: Combine the jeans with a light-blue button-down shirt, a pair of brown boots, and a brown leather belt. Add a casual jacket or a cardigan for a relaxed, weekend vibe. Remember, these are just starting points, and you can always experiment with different pieces and styles to create your own unique look. Since your wardrobe is empty, you can start building it around this great thrifted find! |
| `create_fit_card` | `outfit` argument is empty or whitespace-only | Returns a descriptive fallback string using `new_item` metadata (category, colors, style tags) — does not raise or call the LLM | No viable outfits could be found for the Vintage Levi's 501 Jeans — Medium Wash. As a general tip, this bottoms in blue, indigo with a vintage, classic, denim, streetwear vibe pairs well with neutral basics or statement pieces that complement its color palette. |

# Spec Reflection

**One way the spec helped:** The error handling table in `planning.md` forced explicit decisions about each failure mode before any code was written — specifically that `search_listings` returning an empty list must cause an immediate early return with a descriptive error message, preventing `suggest_outfit` from ever being called with `None` input. Without the table, this guard would have been easy to overlook.

**One divergence from the spec:** Three logic bugs were found and fixed post-implementation. (1) `search_listings` stripped punctuation from keywords and switched to whole-word matching — the original substring check caused false positives (e.g. `"red"` matching `"shredded"`) and false negatives from punctuation like `"vintage,"`. (2) The size filter was changed from substring to token comparison (splitting on `/`) — the original `in` check let through wrong sizes (e.g. `"m"` matching `"medium"` or `"denim"`). (3) `suggest_outfit` was accessing `w.get('color')` and `w.get('style')` but the wardrobe schema uses `colors` (list) and `style_tags` (list) — these always returned `None`, so wardrobe descriptions sent to the LLM were always `"unknown color, unknown style"` regardless of actual wardrobe content.

# AI Usage

**Instance 1: `create_fit_card` fallback behavior**

Input given to AI: the Tool 3 spec section from `planning.md` — specifically the docstring requirement that an empty or whitespace-only `outfit` argument must return a descriptive error string and must not raise an exception or call the LLM.

What it produced: an implementation that raised a `ValueError` on empty input instead of returning a string, which would have crashed the agent loop rather than gracefully surfacing an error to the UI.

What was changed: overrode the exception-raising behavior entirely. The final implementation returns a fallback string built from `new_item` metadata (`category`, `colors`, `style_tags`) so the UI always receives a displayable string and the agent loop never breaks on this path.

---

**Instance 2: unit test structure**

Input given to AI: the completed `tools.py` file and a request to generate tests covering each tool's behavior.

What it produced: a flat set of basic `assert` checks with no fixtures, no mocking of the Groq client, and no isolation between tests — meaning every test would make real API calls and share global state.

What was changed: restructured the entire test file to production-level pytest standards — `@pytest.fixture` for shared test data (`sample_item`, `example_wardrobe`, `empty_wardrobe`), `unittest.mock.patch` with `MagicMock` to mock `_get_groq_client` so no real API calls are made, and prompt-capture tests (using `side_effect`) that assert the correct content appears in the LLM prompt rather than just asserting a non-empty string is returned.
