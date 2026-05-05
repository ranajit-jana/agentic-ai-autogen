# Agentic AI ADK — Feedback Pipeline

An agentic feedback processing pipeline built with **Google ADK** and **Claude (via LiteLLM)**. It reads app store reviews and support emails, classifies them, extracts structured information, and creates actionable engineering tickets — all orchestrated through a multi-agent graph with a Streamlit UI for control and monitoring.

---

## Architecture

```
data/input/
  app_store_reviews.csv
  support_emails.csv
        │
        ▼
  CSVReaderAgent          reads and normalises all feedback items
        │
        ▼
  ClassifierAgent         categorises each item (Bug / Feature Request /
        │                 Praise / Complaint / Spam) with confidence score
        │
   ┌────┴─────┐
   │          │
BugAnalysis  FeatureExtractor   specialised agents for structured extraction
   │          │
   └────┬─────┘
        │
  QualityCriticAgent      validates completeness before ticket creation
        │
  TicketCreatorAgent      writes final tickets to data/output/
```

All LLM agents are powered by `claude-sonnet-4-6` through **Google ADK** with **LiteLLM** as the model bridge.

---

## Tech Stack

| Layer | Library |
|-------|---------|
| Agent framework | [Google ADK](https://google.github.io/adk-docs/) (`google-adk`) |
| LLM provider | Anthropic Claude (`anthropic`) |
| Model bridge | [LiteLLM](https://docs.litellm.ai/) (`litellm`) |
| Observability | [Langfuse](https://langfuse.com/) (`langfuse`) |
| UI | Streamlit |
| Data | pandas |

### Why LiteLLM?

Google ADK is built around Gemini models. **LiteLLM** is a unified interface that normalises 100+ LLM providers (Anthropic, OpenAI, Cohere, Mistral, and more) into a single API. It acts as the bridge between ADK and Claude, so you can swap providers by changing a single model string — no other code changes needed.

```python
# ADK agent using Claude via LiteLLM
Agent(
    name="classifier",
    model=LiteLlm(model="anthropic/claude-sonnet-4-6"),
    instruction=system_prompt,
)
```

The model string format is `"provider/model-name"` — LiteLLM routes it to the correct API automatically.

---

## How Agents Work

Each agent follows the same stateless pattern:

1. Build a structured prompt from the pipeline state
2. Call `_invoke_agent()` — a module-level function that creates a fresh `InMemorySessionService` and `Runner` per call
3. Stream the ADK response events and collect the final text
4. Parse and validate the JSON output via Pydantic

```python
async def _invoke_agent(agent: Agent, prompt: str) -> str:
    session_service = InMemorySessionService()
    session = session_service.create_session(app_name=_APP_NAME, user_id="pipeline")
    runner = Runner(agent=agent, app_name=_APP_NAME, session_service=session_service)
    content = types.Content(role="user", parts=[types.Part(text=prompt)])
    text = ""
    async for event in runner.run_async(
        user_id="pipeline", session_id=session.id, new_message=content
    ):
        if event.is_final_response() and event.content:
            for part in event.content.parts:
                if hasattr(part, "text") and part.text:
                    text += part.text
    return text
```

Each call gets its own isolated session — no accumulated history across feedback items.

---

## Prerequisites

| Requirement | Version |
|-------------|---------|
| Python | ≥ 3.13 |
| uv | any recent |
| Anthropic API key | — |
| Langfuse API key | — |

---

## Setup

**1. Install uv**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

**2. Clone and enter the project**

```bash
cd agentic-ai-google-adk
```

**3. Create the virtual environment and install dependencies**

```bash
uv sync
```

**4. Add your API keys**

Create a `.env` file in the project root (never commit this file):

```bash
# Anthropic — required for all agents
ANTHROPIC_API_KEY=your-anthropic-key-here

# Langfuse — required for pipeline tracing / observability
LANGFUSE_PUBLIC_KEY=your-langfuse-public-key-here
LANGFUSE_SECRET_KEY=your-langfuse-secret-key-here
LANGFUSE_HOST=https://cloud.langfuse.com   # or your self-hosted URL
```

Both services are required. The pipeline will fail to initialise if either key is missing.

- Get your Anthropic key at **console.anthropic.com**
- Get your Langfuse keys at **cloud.langfuse.com → Settings → API Keys**

**5. Verify**

```bash
python -c "import anthropic, google.adk, litellm, streamlit; print('All packages OK')"
```

---

## Generating Dummy Data

Before running the pipeline you need seed data in `data/input/`. The generator is pure Python — no API calls, runs in under a second.

```bash
uv run data-gen/generate.py
```

This writes three files:

| File | Default rows |
|------|-------------|
| `data/input/app_store_reviews.csv` | 120 |
| `data/input/support_emails.csv` | 60 |
| `data/input/expected_classifications.csv` | 180 |

**Options**

```bash
uv run data-gen/generate.py --reviews 200 --emails 100 --seed 42
```

| Flag | Default | Description |
|------|---------|-------------|
| `--reviews` | 120 | Number of app reviews (no hard ceiling) |
| `--emails` | 60 | Number of support emails (no hard ceiling) |
| `--output` | `data/input` | Output directory |
| `--seed` | random | Fix seed for reproducible output |

---

## Running the Pipeline (CLI)

```bash
uv run python pipeline.py
```

Optional flags:

```bash
uv run python pipeline.py --limit 50   # process only the first 50 items
```

Output files appear in `data/output/`:

| File | Contents |
|------|----------|
| `generated_tickets.csv` | All created tickets |
| `processing_log.csv` | Per-item agent trace with confidence scores |
| `metrics.csv` | Summary stats per pipeline run |

---

## Running the Streamlit UI

```bash
streamlit run app.py
```

The app opens at **http://localhost:8501** in your browser.

---

## Navigating the Streamlit UI

The sidebar has five pages. Use the radio buttons to switch between them.

---

### Dashboard

The landing page. Shows a live summary of all tickets generated so far.

| Section | What it shows |
|---------|--------------|
| KPI row | Total tickets, bugs, feature requests, critical items, pipeline run count |
| Category Breakdown | Donut chart — proportion of each feedback category |
| Priority Distribution | Bar chart — ticket counts by priority level |
| Latest Run | Stats from the most recent pipeline execution |
| Recent Tickets | Table of the 10 most recently created tickets |

Click **Refresh data** in the sidebar at any time to reload from disk.

---

### Generate Dummy Data

Use this page to seed `data/input/` with realistic dummy data without leaving the browser.

**Settings panel (left)**

- **App Reviews** — how many app store reviews to generate (10 – 1,000)
- **Support Emails** — how many support emails to generate (5 – 500)
- **Fix random seed** — tick this to get the same data every time you generate
- **Seed value** — the seed number (only active when the checkbox is ticked)
- Output preview shows the expected row count for each file before you generate

**Generate panel (right)**

- A warning appears if existing files in `data/input/` will be overwritten
- Click **Generate Dummy Data** to run the generator; output is shown in an expandable log
- **Current Files** lists each CSV with its row count, column count, and file size

Data distribution generated:

| Category | Reviews | Emails |
|----------|---------|--------|
| Bug | 30 % | 60 % |
| Feature Request | 25 % | 40 % |
| Praise | 20 % | — |
| Complaint | 15 % | — |
| Spam | 10 % | — |

---

### Configure & Run

Run the pipeline and tune its settings.

**Classification Settings (left)**

- **Confidence Threshold** — items whose classifier confidence falls below this value are skipped and not turned into tickets (default 0.70)
- **Default Priority by Category** — set the fallback priority for Bug, Feature Request, and Complaint tickets
- **Item Limit** — cap how many feedback items are processed in one run (0 = all)

**Run panel (right)**

- A summary box shows the active settings before you commit
- Click **Run Pipeline** to execute; a spinner appears while it runs (typically 1–5 minutes depending on item count and API latency)
- Pipeline stdout/stderr is shown in an expandable log after completion
- **Current Config** shows the exact JSON config that was passed to the pipeline

---

### Tickets

Browse, filter, and manually edit generated tickets.

**Filters (top row)**

- **Category** — multi-select; defaults to all five categories
- **Priority** — multi-select; defaults to all four priority levels
- **Source** — filter by `review` or `email` origin

**Editable table**

- Inline editing for Category, Priority, Title, and Technical Details
- Click **Save changes** to write edits back to `data/output/generated_tickets.csv`

**Ticket Detail (bottom)**

- Select any ticket from the dropdown to view and edit its full description
- Edit Title, Description, and Technical Details then click **Save this ticket**

---

### Analytics

Deeper charts across all pipeline runs.

| Section | What it shows |
|---------|--------------|
| Run History | Table of every pipeline run with success rate |
| Tickets Created per Run | Stacked bar — created / skipped / failed per run |
| Category Distribution | Bar chart across all runs combined |
| Confidence Score Distribution | Histogram of classifier confidence scores with threshold line |
| Agent Step Counts | Bar chart of how many times each agent was invoked |
| Ticket Priority by Category | Grouped bar — priority breakdown within each category |
| Aggregate Statistics | Totals across all runs — processed, created, skipped, failed, overall success rate |

---

## Running the Tests

```bash
uv run pytest tests/ \
    --cov=agents \
    --cov-report=term-missing \
    --cov-report=html:reports/htmlcov \
    --junitxml=reports/test-report.xml \
    -v
```

Open the HTML coverage report:

```bash
xdg-open reports/htmlcov/index.html   # Linux
open reports/htmlcov/index.html       # macOS
```

---

## Project Structure

```
agentic-ai-google-adk/
├── app.py                  Streamlit UI
├── pipeline.py             Pipeline entry point (CLI)
├── config.py               Paths, model name, thresholds
├── logger.py               PipelineLogger utility
├── agents/
│   ├── csv_reader_agent.py
│   ├── classifier_agent.py
│   ├── bug_analysis_agent.py
│   ├── feature_extractor_agent.py
│   ├── quality_critic_agent.py
│   ├── ticket_creator_agent.py
│   ├── state.py
│   └── tracer.py
├── data-gen/
│   └── generate.py         Dummy data generator
├── data/
│   ├── input/              Seed CSVs (source data)
│   └── output/             Generated tickets, logs, metrics
├── tests/                  pytest test suite
├── pyproject.toml
└── setup.txt               Step-by-step setup reference
```
