# HOPE

[![Tests](https://github.com/PavanMutyla/HOPE/actions/workflows/test.yml/badge.svg)](https://github.com/PavanMutyla/HOPE/actions/workflows/test.yml)

HOPE is a voice-first AI colleague that runs on your own machine. You talk to it out loud, and it answers in its own voice. It can hand work to other agents, and each one speaks in a voice of its own. That includes **researchers HOPE spawns on demand**: they search the web in parallel, and you can talk to them by name.

```
           you (microphone)
                 │
   ┌─────────────▼──────────────────────────────────────────────┐
   │  one shared voice pipeline (pipecat)                       │
   │  mic → Silero VAD → Smart Turn → STT → LLM → Kokoro TTS → 🔊│
   └─────────────┬──────────────────────────────────────────────┘
                 │  whoever is "active" owns the pipeline:
     ┌───────────┼──────────────┬──────────────────────────┐
   HOPE       Atlas        Emma · Michael · …          (team mode:
  (host)   (filesystem)   (researchers, spawned       agents can also
                           per task, own voices)       chime in on their
                                                        own voice)
                 │
   memory: working · episodic · semantic · procedural
   shared state: blackboard (tasks, agents, research) · corkboard
   dashboard: Reflex web app, read-only, at http://localhost:3000
```

---

## Contents

- [What it does](#what-it-does)
- [Requirements](#requirements)
- [Installation](#installation)
- [Setting up web search (degoog)](#setting-up-web-search-degoog)
- [Running HOPE](#running-hope)
- [Talking to HOPE](#talking-to-hope)
- [Configuration reference](#configuration-reference)
- [What leaves your machine](#what-leaves-your-machine)
- [Safety model](#safety-model)
- [Architecture](#architecture)
- [Voices](#voices)
- [Testing](#testing)
- [Troubleshooting](#troubleshooting)
- [Known limitations](#known-limitations)
- [Open-source credits and licenses](#open-source-credits-and-licenses)
- [License](#license)

---

## What it does

**Voice conversation**
- A full-duplex voice loop on your local audio devices, with no browser involved. Silero detects speech, and the Smart Turn model decides when you've actually finished talking, rather than just pausing.
- Speech is generated locally by **Kokoro** (82M parameters, ONNX on CPU). Speech-to-text and the conversation LLM use OpenAI.

**Agents**
- **HOPE**: the host. It talks with you, decides what to delegate, and relays results.
- **Atlas**: a filesystem worker, locked to a single workspace directory. It creates, reads, edits and deletes files in the background while you keep talking.
- **Researchers** (spawned at runtime): ask HOPE to research something properly. It plans subtopics and spawns 1–4 researchers, each with its own name and voice. They search the web in parallel and HOPE gets back a cited report. While a researcher is working, or after it finishes, you can say *"let me talk to Emma"* to ask it what it found.
- **Team mode** (opt-in): other agents listen in and can speak up on their own voice, at the same time as HOPE.

**Memory**, four tiers:
- **Working**: the live conversation. It's summarized automatically once it gets close to the context limit.
- **Episodic**: every summary, finished task and finished session, in SQLite plus a Chroma vector index. It's searchable with `recall_memory`.
- **Semantic**: durable facts about you, extracted by Mem0. Searchable with `recall_semantic`.
- **Procedural**: step-by-step procedures you explicitly ask HOPE to remember. Stored as hand-editable markdown in `procedures/`.

**Shared state**
- **Blackboard**: a SQLite task/signal pool agents use to hand each other work. It also holds the spawned agents and research runs.
- **Corkboard**: Today / Planned / Pending lists plus a quick note. You, HOPE and Atlas all edit the same rows.

**Dashboard**: a read-only Reflex web app showing:
- the conversation in progress, plus every past one
- the corkboard
- a live log tail

It's read-only by design: HOPE takes voice input only, so there's no chat box.

---

## Requirements

| What | Notes |
|---|---|
| **OS** | Developed and tested on **Linux** (Pop!_OS / Ubuntu 24.04, PipeWire). macOS may work but is untested. Windows is untested. |
| **Python** | **3.11 or 3.12**. 3.13 is not supported, because pipecat still uses `audioop`, which was removed in 3.13. |
| **Poetry** | For dependencies: <https://python-poetry.org/docs/#installation> |
| **PortAudio** | Needed by PyAudio for the microphone and speakers. Ubuntu/Debian: `sudo apt install portaudio19-dev libportaudio2` |
| **Microphone + speakers** | Your default input and output devices are used. Headphones help prevent HOPE hearing itself. |
| **`curl`, `unzip`, `git`** | Reflex downloads its own Bun runtime on first run and needs `curl` and `unzip` to do it. |
| **Disk** | About 1 GB for the Python environment, about 330 MB of Kokoro model files, and about 80 MB for Chroma's embedding model. |
| **OpenAI API key** | Required: speech-to-text, HOPE's LLM, Atlas, summarization, Mem0, and research. |
| **Langfuse keys** | Required by the settings. Use a free [Langfuse Cloud](https://cloud.langfuse.com) project or [self-host](https://langfuse.com/self-hosting). |
| **Bun** (optional) | Only needed to run **degoog** natively for web search. See [below](#setting-up-web-search-degoog). |

No GPU is needed. Kokoro, Silero and Smart Turn all run on the CPU through ONNX Runtime.

---

## Installation

```bash
# 1. System packages (Ubuntu/Debian)
sudo apt update
sudo apt install -y python3.12 python3.12-venv portaudio19-dev libportaudio2 curl unzip git

# 2. Poetry, if you don't have it
curl -sSL https://install.python-poetry.org | python3 -

# 3. Clone
git clone https://github.com/PavanMutyla/HOPE.git
cd HOPE

# 4. Python environment (creates .venv/ in the project)
poetry config virtualenvs.in-project true
poetry env use python3.12
poetry install

# 5. Configuration
cp .env.example .env
$EDITOR .env          # set OPENAI_API_KEY, USER_NAME, LANGFUSE_*, ATLAS_WORKSPACE at minimum
mkdir -p "$(grep ^ATLAS_WORKSPACE .env | cut -d= -f2)"
```

`ATLAS_WORKSPACE` must be an absolute path. **It's the only directory Atlas can read or write.** Point it at a scratch folder, not your home directory.

**First-run downloads** happen automatically:
- Kokoro's `kokoro-v1.0.onnx` and `voices-v1.0.bin`, about 330 MB from the [kokoro-onnx releases](https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0). They're cached in `~/.cache/pipecat/kokoro-onnx/` and re-downloaded automatically if a previous download was cut short.
- Chroma's `all-MiniLM-L6-v2` embedding model, about 80 MB, the first time episodic memory is used.
- Reflex's Bun and Node packages for the dashboard, on its first start.

The Silero VAD and Smart Turn v3 models ship inside the `pipecat-ai` package.

---

## Setting up web search (degoog)

HOPE never uses a search vendor's API for web search. It queries a **meta-search engine you run yourself**, which fans each query out to upstream engines (Google, Bing, DuckDuckGo, Brave and others) and merges the results. The default is [**degoog**](https://github.com/degoog-org/degoog), with [**SearXNG**](https://github.com/searxng/searxng) as a drop-in alternative.

Without one running, everything else still works. `search_web` and deep research just reply that the search engine isn't reachable.

### Option A: degoog, native (needs Bun)

```bash
curl -fsSL https://bun.sh/install | bash        # if you don't have bun
git clone https://github.com/degoog-org/degoog.git ~/degoog
cd ~/degoog
echo 'DEGOOG_SETTINGS_PASSWORDS=pick-a-real-password' > .env
bun install
bun run build
bun run start                                   # listens on :4444
```

### Option B: degoog, Docker

```bash
mkdir -p ~/degoog/data && sudo chown 1000:1000 ~/degoog/data
docker run -d --name degoog --restart unless-stopped \
  -p 127.0.0.1:4444:4444 \
  -v ~/degoog/data:/app/data \
  -e DEGOOG_SETTINGS_PASSWORDS=pick-a-real-password \
  ghcr.io/degoog-org/degoog:latest
```

**Always set `DEGOOG_SETTINGS_PASSWORDS`.** degoog extensions run code on its server, so an unlocked settings page lets anyone who can reach it install code. Bind it to `127.0.0.1` as shown, unless you mean to share it. If HTTPS requests fail with certificate errors, install `ca-certificates`.

Check that it works:

```bash
curl 'http://localhost:4444/api/search?q=kokoro+tts' | head -c 300
```

If you lock the search API with an API key in degoog's settings, put it in `DEGOOG_API_KEY`.

### Option C: SearXNG instead

Run SearXNG ([install docs](https://docs.searxng.org/admin/installation.html)). In its `settings.yml`, enable JSON output, which is off by default; without it, HOPE gets a 403:

```yaml
search:
  formats:
    - html
    - json
```

Then set `SEARCH_PROVIDER=searxng` and `SEARXNG_URL=http://localhost:8888` (or wherever it listens) in `.env`.

---

## Running HOPE

```bash
poetry run python hope.py
# or: .venv/bin/python hope.py
```

- **Wait for the greeting.** HOPE says hello once the pipeline is up. The first launch takes longer while the models download.
- **The terminal shows the dashboard's (Reflex's) output**, plus the URL, normally <http://localhost:3000>. HOPE's own logs go to `data_store/logs/hope.log`, and the dashboard's log card shows them live.
- **Stop with `Ctrl+C`.** HOPE saves the session to episodic memory, retires any spawned researchers, and shuts down the dashboard.
- **To run without the dashboard,** set `DASHBOARD_AUTOSTART=false`.

Everything HOPE stores is in `data_store/` (gitignored). Delete that folder to start from a clean slate.

---

## Talking to HOPE

Just talk; there are no wake words. Some examples of what each capability responds to:

| Say something like… | What happens |
|---|---|
| "Create a file called notes.md with today's plan" | HOPE delegates it to **Atlas**, which works in the background |
| "Let me talk to Atlas" / "Back to HOPE" | The voice switches agents (`connect_to_agent` / `handback_to_hope`) |
| "What's the latest Python release?" | A quick **web search** (`search_web`, `read_webpage`) |
| "Research the best open-source TTS models and compare them" | **Deep research**: researchers are spawned and a cited report comes back |
| "How's the research going?" / "Who's working on it?" | `research_status` / `list_subagents` |
| "Let me talk to Emma" | You talk to that researcher directly, in its own voice |
| "Thanks, you can dismiss Emma" | `retire_subagent` frees its voice |
| "Bring the team in" / "Just us" | Team mode on / off |
| "Add 'call the bank' to today" | Edits the shared **corkboard** |
| "What did we talk about last week about the launch?" | **Episodic memory** recall |
| "Remember this as a procedure: …" | Saves a **procedure** (only when you ask explicitly) |
| "What's the weather?" | Local weather (Open-Meteo) |

**Deep research output** lands in `data_store/research/<run_id>/`:
- `report.md`: the final cited report
- `<name>.md`: one file of findings per researcher

Every page a researcher read is saved under `data_store/research/pages/`, so the citations can be checked against exactly what it saw.

---

## Configuration reference

All settings are read from `.env` by [`settings.py`](settings.py) (pydantic-settings). `.env.example` lists every key.

**Required**

| Key | Purpose |
|---|---|
| `OPENAI_API_KEY` | Speech-to-text, LLMs, summarization, Mem0 |
| `USER_NAME` | Your name. It scopes semantic memory to you. |
| `LOG_LEVEL` | e.g. `INFO` |
| `STT_MODEL` | OpenAI transcription model, e.g. `gpt-4o-mini-transcribe` |
| `LLM_MODEL` | HOPE's conversation model, e.g. `gpt-4.1-mini` |
| `LLM_PROVIDER` | litellm provider prefix used to look up the context window, e.g. `openai` |
| `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY`, `LANGFUSE_BASE_URL` | Tracing |
| `ATLAS_LLM_MODEL` | Atlas's model, e.g. `gpt-4o-mini` |
| `ATLAS_WORKSPACE` | Absolute path. The only directory Atlas may touch. |

**Optional, with their defaults**

| Key | Default | Purpose |
|---|---|---|
| `KOKORO_VOICE_ID` | `af_heart` | HOPE's voice |
| `KOKORO_ATLAS_VOICE_ID` | `af_bella` | Atlas's voice |
| `SEARCH_PROVIDER` | `degoog` | `degoog` or `searxng` |
| `DEGOOG_URL` | `http://localhost:4444` | |
| `DEGOOG_API_KEY` | *(empty)* | Only if degoog's search API is locked |
| `SEARXNG_URL` | `http://localhost:8888` | |
| `MAX_LIVE_SUBAGENTS` | `5` | Hard cap on spawned agents alive at once |
| `RESEARCH_LLM_MODEL` | `gpt-4o-mini` | Planner, researchers, and report writer |
| `RESEARCH_MAX_RESEARCHERS` | `4` | Most researchers one run can spawn |
| `RESEARCH_MAX_TOOL_CALLS` | `12` | Search and read budget per researcher |
| `SUMMARIZER_MODEL` | `gpt-4o-mini` | Context folding and Mem0's LLM |
| `LLM_CONTEXT_LIMIT` | `128000` | Fallback only; the real window is looked up per model |
| `CONTEXT_SUMMARIZE_THRESHOLD` | `0.9` | Fold older turns once the context is this full |
| `CONTEXT_KEEP_RECENT` | `6` | Turns kept verbatim after a fold |
| `HOME_CITY`, `HOME_LAT`, `HOME_LON` | *(empty = detect from IP)* | Weather location override |
| `DASHBOARD_AUTOSTART` | `true` | Start the dashboard with HOPE |
| `*_DB_PATH`, `*_DIR`, `HOPE_LOG_PATH` | under `data_store/` | Storage locations. Keep them absolute, because the dashboard runs from a different working directory. |

---

## What leaves your machine

HOPE is local-first, not fully offline. This is exactly what goes where:

| Data | Goes to | Why |
|---|---|---|
| Your speech audio | **OpenAI** | Speech-to-text |
| Conversation text, tool results, context summaries | **OpenAI** | HOPE's and Atlas's LLM, summarization |
| Facts extracted from conversations | **OpenAI** | Mem0 extraction and embeddings |
| Research questions and the page text researchers read | **OpenAI** | The planner, researcher and writer LLMs |
| Traces of LLM calls | **Langfuse** (cloud or your own instance) | Observability |
| Search queries | **Upstream search engines**, via your degoog/SearXNG instance, from your IP | Web search |
| Page requests | **The websites themselves** | Reading pages |
| Your IP address | **ipwho.is** | Location for the weather card (skipped if `HOME_LAT`/`HOME_LON` are set) |
| Latitude and longitude | **Open-Meteo** | Weather |

**Stays local:**
- Text-to-speech, plus voice and turn detection
- Every database and memory file
- Episodic embeddings (Chroma's local model)
- Procedures and the dashboard

To keep the LLM local too, `LLM_PROVIDER` and litellm can point at a local model server. That path isn't tested yet.

---

## Safety model

Agents can read the open web, and a web page can contain text written to manipulate an agent. So the key rules are enforced **in code**, not only in prompts:

- **Researchers are read-only.** Their whole tool table is `web_search` and `read_url` ([`sub_agents/research/toolbox.py`](sub_agents/research/toolbox.py)). A sub-agent spec that asks for any other tool fails validation ([`core/agents/spec.py`](core/agents/spec.py)).
- **No reaching into your machine or network.** [`tools/web/fetch.py`](tools/web/fetch.py) does GET only, with no cookies and http/https only. It refuses any host that resolves to localhost or a private, link-local or CGNAT address, and it re-checks every redirect hop. Size, time and content type are capped. A page therefore can't make an agent call degoog, the dashboard or your router.
- **Web text is labelled.** Everything from the web is wrapped in `<untrusted_web_content>` tags, and every prompt treats it as data, never instructions.
- **Connected researchers are gated.** While you're talking to a researcher, every tool except hand-back, connect and status is refused ([`tools/registry.py`](tools/registry.py) `_guarded`). Findings derived from the web can't trigger Atlas or edit your corkboard.
- **Hard limits:** live sub-agents, researchers per run and tool calls per researcher are all capped in code.
- **Atlas is jailed** to `ATLAS_WORKSPACE`. Path traversal is rejected.
- **Web research never enters semantic memory**, so an article's claim can't become a "fact about you".

Known gap: the fetcher's address check and its connection do separate DNS lookups, so a hostile DNS server could still attempt DNS rebinding. The details are documented in `tools/web/fetch.py`.

---

## Architecture

```
hope.py                  entrypoint: registers agents, builds the pipeline, wires tools, starts the dashboard
settings.py              all configuration (pydantic-settings, .env)
core/
  voice/
    pipeline.py          build_pipeline(): transport, STT, LLM, Kokoro TTS, VAD and turn detection, observers
    agent.py             VoiceAgent + AgentRegistry (switch = swap system prompt + TTS voice)
    orchestrator.py      VoiceOrchestrator: switch_to, agent_to_agent (text-only), broadcast
    voice_pool.py        VoicePool: one distinct Kokoro voice + spoken name per spawned agent
    summarizer.py        ContextSummarizer: folds old turns, writes episodic + semantic memory
    team_*.py            team mode: TeamVoice (independent audio stream), registry, broadcast observer
    live_feed.py         writes live turns/state for the dashboard
  agents/
    spec.py              SubAgentSpec + per-template tool allowlist
    manager.py           SubAgentManager: spawn/retire, keeps registry, voice pool and DB in step
  prompt.py              HOPE's system prompt
sub_agents/
  atlas/                 filesystem agent: background runner, tools, voice and team prompts
  research/              deep research: workflow, read-only toolbox, prompts
tools/
  registry.py            every tool schema exposed to HOPE + its handler + the sub-agent guard
  schema.py              pydantic argument models (single source of truth for tool parameters)
  web/                   search providers (degoog, SearXNG) and the guarded page fetcher
memory/
  episodic_memory/       SQLite + Chroma: episodes, plans, media
  semantic_memory/       Mem0 wrapper
  procedural_memory/     markdown procedures in procedures/<agent>/
  coordination/          blackboard: tasks, signals, agents, research runs, sources
  board/                 corkboard lists + quick note, location/weather
  live/                  the live feed the dashboard polls
dashboard/               Reflex app (its own process, talks to hope.py only through SQLite)
tests/                   unit / integration / contract suites
```

Design notes worth knowing:
- **One pipeline, many agents.** Switching agents swaps the system prompt and pushes a TTS voice-change frame. Agent-to-agent traffic is text only, with no TTS cost.
- **Background work doesn't block talking.** Atlas and deep research run as asyncio tasks and report back through the tool's result callback.
- **Two processes, one source of truth.** The dashboard never touches the pipeline's memory. It reads the same SQLite files in WAL mode, which is why every data path in `settings.py` is absolute.

---

## Voices

Kokoro ships 54 voices in 9 languages ([full list and grades](https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md)). HOPE uses the English ones:

- **HOPE**: `af_heart` (grade A)
- **Atlas**: `af_bella` (A-)
- **Spawned agents**: leased from this pool, best first, alternating female and male:

| Voice | Name | | Voice | Name |
|---|---|---|---|---|
| af_nicole | Nicole | | af_kore | Kore |
| am_michael | Michael | | bm_george | George |
| bf_emma | Emma | | af_aoede | Aoede |
| am_fenrir | Fenrir | | bm_fable | Fable |
| af_sarah | Sarah | | bf_isabella | Isabella |
| am_puck | Puck | | af_nova | Nova |

Naming: `a`/`b` = American/British English, `f`/`m` = female/male. To change a voice, set `KOKORO_VOICE_ID` / `KOKORO_ATLAS_VOICE_ID`, or edit `POOL` in [`core/voice/voice_pool.py`](core/voice/voice_pool.py).

---

## Testing

```bash
.venv/bin/pytest                 # everything (~10 s, no network, no audio, no API keys)
.venv/bin/pytest -m unit
.venv/bin/pytest -m integration
.venv/bin/pytest -m contract     # interface compliance for swappable LLM/STT/TTS/VAD/search/tools
.venv/bin/ruff check .
```

The suite forces fake credentials and temp data paths before anything is imported, so it never touches your real `.env` or `data_store/`. Tests that call real APIs are named `test_*_live.py` and only run with `RUN_LIVE_TESTS=1`. CI runs the full suite on every push.

---

## Troubleshooting

| Symptom | Fix |
|---|---|
| `pyaudio` fails to build during `poetry install` | `sudo apt install portaudio19-dev`, then reinstall |
| `ValidationError` at startup | A required key is missing from `.env`. The error names it. |
| HOPE hears itself and keeps replying | Use headphones, or lower the speaker volume |
| "degoog isn't reachable at …" | Start degoog, or check `DEGOOG_URL` |
| "searxng refused JSON output" | Enable `json` in SearXNG's `search.formats` |
| Kokoro fails to load on first run | An interrupted download. HOPE deletes the partial files and retries once; delete `~/.cache/pipecat/kokoro-onnx/` if it keeps failing. |
| Dashboard empty, or shows HOPE as down | It treats a heartbeat older than 30 s as "not running". Check `data_store/logs/hope.log`. |
| Port 3000 already in use | Reflex picks another port and prints it in the terminal |

---

## Known limitations

- **Personal by default.** HOPE's system prompt ([`core/prompt.py`](core/prompt.py)) is written for its author and calls the user "Pavan". Edit it for your own use.
- **Atlas** can only work on one task at a time.
- **Deep research** runs one at a time, takes a few minutes, and costs real API money (multi-agent research uses many times the tokens of a normal chat).
- **Sub-agents are disposable.** They live only as long as the `hope.py` process.
- **Researchers can't run JavaScript.** Pages that need it come back with little or no text.
- **Browser voice isn't built.** You talk to HOPE through the microphone of the machine running it.

---

## Open-source credits and licenses

HOPE is built on the work of many open-source projects. Thank you to all of them. Licenses are as published by each project when this was written; check upstream before redistributing.

### Voice and audio

| Project | Used for | License |
|---|---|---|
| [Pipecat](https://github.com/pipecat-ai/pipecat) | The real-time voice pipeline framework | BSD-2-Clause |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) by hexgrad | Text-to-speech model and the 54 voices | Apache-2.0 |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | ONNX runtime wrapper for Kokoro; hosts the model files | MIT |
| [eSpeak NG](https://github.com/espeak-ng/espeak-ng), via [espeakng-loader](https://pypi.org/project/espeakng-loader/) | Phonemization for Kokoro (bundled `libespeak-ng`) | GPL-3.0 (eSpeak NG) |
| [phonemizer-fork](https://pypi.org/project/phonemizer-fork/) ([phonemizer](https://github.com/bootphon/phonemizer)) | Text → phonemes for Kokoro | GPL-3.0-or-later |
| [Silero VAD](https://github.com/snakers4/silero-vad) | Voice activity detection | MIT |
| [Smart Turn v3](https://github.com/pipecat-ai/smart-turn) | End-of-turn detection model | BSD-2-Clause |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | Runs Kokoro, Silero, Smart Turn and embeddings on the CPU | MIT |
| [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) / [PortAudio](https://www.portaudio.com/) | Microphone and speaker I/O | MIT / MIT-style |

### Memory, data and agents

| Project | Used for | License |
|---|---|---|
| [Mem0](https://github.com/mem0ai/mem0) | Semantic memory (fact extraction) | Apache-2.0 |
| [Chroma](https://github.com/chroma-core/chroma) | Vector index for episodic and semantic memory | Apache-2.0 |
| [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Chroma's default local embedding model | Apache-2.0 |
| [SQLite](https://sqlite.org) | Every database | Public domain |
| [LiteLLM](https://github.com/BerriAI/litellm) | Model context-window lookup across providers | MIT |
| [OpenAI Python SDK](https://github.com/openai/openai-python) | API client | Apache-2.0 |
| [Langfuse Python SDK](https://github.com/langfuse/langfuse-python) | Tracing | MIT |
| [python-ulid](https://github.com/mdomke/python-ulid) | Sortable IDs | MIT |
| [PyYAML](https://pyyaml.org/) | Procedure frontmatter | MIT |

### Web access

| Project | Used for | License |
|---|---|---|
| [degoog](https://github.com/degoog-org/degoog) | Default self-hosted meta-search engine (run separately) | AGPL-3.0 |
| [SearXNG](https://github.com/searxng/searxng) | Alternative self-hosted meta-search engine (run separately) | AGPL-3.0 |
| [Trafilatura](https://github.com/adbar/trafilatura) | Main-text extraction from web pages | Apache-2.0 |
| [HTTPX](https://github.com/encode/httpx) | HTTP client | BSD-3-Clause |

### App, config and tooling

| Project | Used for | License |
|---|---|---|
| [Reflex](https://github.com/reflex-dev/reflex) | The dashboard web app | Apache-2.0 |
| [Pydantic](https://github.com/pydantic/pydantic) / [pydantic-settings](https://github.com/pydantic/pydantic-settings) | Data models and configuration | MIT |
| [python-dotenv](https://github.com/theskumar/python-dotenv) | `.env` loading | BSD-3-Clause |
| [Loguru](https://github.com/Delgan/loguru) | Logging | MIT |
| [Rich](https://github.com/Textualize/rich) | Terminal status panel | MIT |
| [NumPy](https://numpy.org) | Audio buffers | BSD-3-Clause |
| [aiofiles](https://github.com/Tinche/aiofiles) | Async file I/O for Atlas | Apache-2.0 |
| [Send2Trash](https://github.com/arsenetar/send2trash) | Atlas deletes to the trash rather than permanently | BSD-3-Clause |
| [pytest](https://github.com/pytest-dev/pytest), [pytest-asyncio](https://github.com/pytest-dev/pytest-asyncio) | Tests | MIT, Apache-2.0 |
| [Ruff](https://github.com/astral-sh/ruff) | Linting | MIT |
| [Poetry](https://github.com/python-poetry/poetry) | Dependency management | MIT |

### Services and data

| Service | Used for | Terms |
|---|---|---|
| [OpenAI API](https://openai.com/policies) | STT, LLMs, embeddings | Commercial API |
| [Langfuse](https://langfuse.com) | Tracing (cloud, or self-hosted under MIT) | Per plan |
| [Open-Meteo](https://open-meteo.com) | Weather. Weather data by Open-Meteo.com, licensed [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). | Free tier is **non-commercial only**, under 10k calls/day |
| [ipwho.is](https://ipwhois.io) | IP-based location | Free tier: 1,000 requests/day |

### Research and design references

- Anthropic, [*How we built our multi-agent research system*](https://www.anthropic.com/engineering/multi-agent-research-system): the orchestrator → parallel-researchers pattern, effort-scaling rules, structured delegation, and citations.
- LangChain, [Open Deep Research](https://github.com/langchain-ai/open_deep_research), and [GPT Researcher](https://github.com/assafelovic/gpt-researcher): the scope → plan → research → write pipeline shape. Neither is a dependency.
- [Deep Research Agents survey (arXiv 2506.18096)](https://arxiv.org/abs/2506.18096).

**Note on copyleft components.**
- eSpeak NG and phonemizer are GPL-3.0. They're installed as Python dependencies of kokoro-onnx; HOPE doesn't vendor or modify them.
- degoog and SearXNG are AGPL-3.0, and run as separate services that HOPE only calls over HTTP.

If you redistribute HOPE bundled with any of these (a Docker image or a packaged app, say), check their license obligations first.

---

## License

*No license has been chosen yet.* Until a `LICENSE` file is added, all rights are reserved by the author.
