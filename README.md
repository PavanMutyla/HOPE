# HOPE

[![Tests](https://github.com/PavanMutyla/HOPE/actions/workflows/test.yml/badge.svg)](https://github.com/PavanMutyla/HOPE/actions/workflows/test.yml)

A local, voice-first AI assistant. You talk to it out loud and it answers in its own voice. It can hand work to other agents, each with a voice of its own:

- **HOPE**: the host. It talks with you and delegates work.
- **Atlas**: a filesystem worker, locked to one workspace folder.
- **Researchers**: spawned on demand for deep research. They search the web in parallel, and you can talk to any of them by name.

HOPE also has four tiers of memory (working, episodic, semantic, procedural), a shared task board, and a read-only web dashboard.

## Requirements

- Linux (tested on Ubuntu 24.04 / Pop!_OS with PipeWire). macOS and Windows are untested.
- Python 3.11 or 3.12. Not 3.13: pipecat still needs `audioop`.
- [Poetry](https://python-poetry.org/docs/#installation)
- PortAudio, plus `curl` and `unzip` (the dashboard uses them on first run)
- [Bun](https://bun.sh), or Docker, for web search (optional)
- A microphone and speakers. Headphones stop HOPE from hearing itself.
- An OpenAI API key and Langfuse keys ([cloud](https://cloud.langfuse.com) or self-hosted)
- No GPU needed

## Install

```bash
sudo apt install -y python3.12 python3.12-venv portaudio19-dev libportaudio2 curl unzip git

git clone https://github.com/PavanMutyla/HOPE.git
cd HOPE
poetry config virtualenvs.in-project true
poetry env use python3.12
poetry install

cp .env.example .env   # then fill in the required keys below
```

The first run downloads about 330 MB of Kokoro model files to `~/.cache/pipecat/kokoro-onnx/`, plus a small embedding model.

## Web search

Web search goes through [degoog](https://github.com/degoog-org/degoog), a meta-search engine that runs on your machine, and **HOPE starts it for you**:

- **With [Bun](https://bun.sh) installed** (recommended, no sudo): `curl -fsSL https://bun.sh/install | bash`. On the first start, HOPE clones and builds degoog into `data_store/degoog/` (about a minute).
- **Without Bun, with Docker:** HOPE runs the official image instead.
- **Neither:** HOPE still runs; web search just reports that it's off. HOPE never installs Bun or Docker for you.

Either way degoog listens on `127.0.0.1:4444` only. On first start, HOPE installs the Bing, DuckDuckGo and Wikipedia engines with SafeSearch on. degoog's settings page is at <http://localhost:4444/settings>; the password is in `data_store/degoog/settings-password`. Its log is `data_store/logs/degoog.log`. If degoog is already running, HOPE uses it and leaves it alone.

**SearXNG instead:** add `json` to `search.formats` in its `settings.yml`, then set `SEARCH_PROVIDER=searxng` and `SEARXNG_URL` in `.env`.

## Run

```bash
poetry run python hope.py
```

Wait for the greeting, then talk. The dashboard opens in your browser by itself once it's up, at <http://localhost:3000> (the first start takes a minute to compile). Stop with `Ctrl+C`.

The dashboard has three log cards, all drawn from `data_store/logs/hope.log`:

- **Log**: everything HOPE writes.
- **Tools**: each tool HOPE or Atlas calls, and how long it took to answer.
- **Web**: searches, pages read, and researchers spawned and finishing.

Example things to say:

| Say | What happens |
|---|---|
| "Create notes.md with today's plan" | Atlas does it in the background |
| "Let me talk to Atlas" / "Back to HOPE" | Switches voice agent |
| "Research open-source TTS models and compare them" | Spawns researchers; a cited report is saved to `data_store/research/<run_id>/report.md` |
| "Let me talk to Sarah" | Talk to a researcher directly |
| "Add 'call the bank' to today" | Edits the shared board |
| "Bring the team in" / "Just us" | Team mode on / off |

All data lives in `data_store/` (gitignored). Delete it to reset.

## Configuration

`.env.example` lists every key, and [`settings.py`](settings.py) holds the defaults.

**Required:** `OPENAI_API_KEY`, `USER_NAME`, `LOG_LEVEL`, `STT_MODEL`, `LLM_MODEL`, `LLM_PROVIDER`, `ATLAS_LLM_MODEL`, `ATLAS_WORKSPACE`, `LANGFUSE_PUBLIC_KEY`, `LANGFUSE_SECRET_KEY` and `LANGFUSE_BASE_URL`.

`ATLAS_WORKSPACE` must be an absolute path to a scratch folder. It's the only place Atlas can read or write.

**Common optional keys:**

| Key | Default | Purpose |
|---|---|---|
| `KOKORO_VOICE_ID` / `KOKORO_ATLAS_VOICE_ID` | `af_heart` / `af_bella` | Voices |
| `SEARCH_PROVIDER` | `degoog` | `degoog` or `searxng` |
| `DEGOOG_URL` / `SEARXNG_URL` | `:4444` / `:8888` on localhost | Search engine address |
| `DEGOOG_AUTOSTART` | `true` | Start degoog with HOPE |
| `DEGOOG_DIR` | `data_store/degoog` | Where HOPE builds degoog |
| `RESEARCH_MAX_RESEARCHERS` | `4` | Researchers per run |
| `RESEARCH_MAX_TOOL_CALLS` | `12` | Searches and reads per researcher |
| `MAX_LIVE_SUBAGENTS` | `5` | Spawned agents alive at once |
| `DASHBOARD_AUTOSTART` | `true` | Start the dashboard with HOPE |
| `DASHBOARD_OPEN_BROWSER` | `true` | Open a browser tab once the dashboard is up |

## Privacy

HOPE is local-first, not offline.

- **Sent to OpenAI:** speech audio, conversation text, and the pages researchers read.
- **Sent to Langfuse:** traces of LLM calls.
- **Sent from your IP:** search queries (through degoog/SearXNG to their upstream engines) and page requests.
- **Weather:** uses ipwho.is and Open-Meteo.
- **Stays local:** text-to-speech, voice and turn detection, and all databases.

## Safety

- **Researchers are read-only.** Their only tools are `web_search` and `read_url`, and this is enforced in code.
- **The page fetcher is restricted.** It does GET only and refuses localhost and private addresses, checking every redirect too.
- **Web text is treated as untrusted data,** never as instructions.
- **Connected researchers are tool-gated.** While you're talking to one, every tool except hand-back, connect and status is refused.
- **Atlas is jailed** to `ATLAS_WORKSPACE`.
- **Web research never goes into semantic memory.**

## Tests

```bash
.venv/bin/pytest        # no network, audio or API keys needed
.venv/bin/ruff check .
```

## Limitations

- The system prompt in `core/prompt.py` addresses the author by name. Edit it for your own use.
- Only one deep research run at a time. Research costs real API money.
- Researchers can't run JavaScript.
- No browser voice yet: you speak through the microphone of the machine running HOPE.

## Credits

Built on these open-source projects (licenses as published upstream):

| Project | Use | License |
|---|---|---|
| [Pipecat](https://github.com/pipecat-ai/pipecat) | Voice pipeline | BSD-2-Clause |
| [Kokoro-82M](https://huggingface.co/hexgrad/Kokoro-82M) | Text-to-speech model and voices | Apache-2.0 |
| [kokoro-onnx](https://github.com/thewh1teagle/kokoro-onnx) | Kokoro runtime | MIT |
| [eSpeak NG](https://github.com/espeak-ng/espeak-ng), [phonemizer](https://github.com/bootphon/phonemizer) | Phonemization (dependencies of kokoro-onnx) | GPL-3.0 |
| [Silero VAD](https://github.com/snakers4/silero-vad) | Voice activity detection | MIT |
| [Smart Turn v3](https://github.com/pipecat-ai/smart-turn) | End-of-turn detection | BSD-2-Clause |
| [ONNX Runtime](https://github.com/microsoft/onnxruntime) | CPU inference | MIT |
| [PyAudio](https://people.csail.mit.edu/hubert/pyaudio/) / [PortAudio](https://www.portaudio.com/) | Audio I/O | MIT |
| [Mem0](https://github.com/mem0ai/mem0) | Semantic memory | Apache-2.0 |
| [Chroma](https://github.com/chroma-core/chroma) + [all-MiniLM-L6-v2](https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2) | Vector index and embeddings | Apache-2.0 |
| [SQLite](https://sqlite.org) | Databases | Public domain |
| [LiteLLM](https://github.com/BerriAI/litellm) | Model context-window lookup | MIT |
| [OpenAI SDK](https://github.com/openai/openai-python) | API client | Apache-2.0 |
| [Langfuse SDK](https://github.com/langfuse/langfuse-python) | Tracing | MIT |
| [degoog](https://github.com/degoog-org/degoog) / [SearXNG](https://github.com/searxng/searxng) | Self-hosted search (separate services) | AGPL-3.0 |
| [Trafilatura](https://github.com/adbar/trafilatura) | Web page text extraction | Apache-2.0 |
| [HTTPX](https://github.com/encode/httpx) | HTTP client | BSD-3-Clause |
| [Reflex](https://github.com/reflex-dev/reflex) | Dashboard | Apache-2.0 |
| [Pydantic](https://github.com/pydantic/pydantic), [pydantic-settings](https://github.com/pydantic/pydantic-settings) | Models and config | MIT |
| [Loguru](https://github.com/Delgan/loguru), [Rich](https://github.com/Textualize/rich) | Logging, terminal UI | MIT |
| [python-ulid](https://github.com/mdomke/python-ulid), [PyYAML](https://pyyaml.org/), [aiofiles](https://github.com/Tinche/aiofiles), [Send2Trash](https://github.com/arsenetar/send2trash), [NumPy](https://numpy.org), [python-dotenv](https://github.com/theskumar/python-dotenv) | Utilities | MIT / Apache-2.0 / BSD |
| [pytest](https://github.com/pytest-dev/pytest), [Ruff](https://github.com/astral-sh/ruff), [Poetry](https://github.com/python-poetry/poetry) | Tooling | MIT |

**Services:**
- [OpenAI API](https://openai.com/policies)
- [Langfuse](https://langfuse.com)
- [Open-Meteo](https://open-meteo.com): weather data under [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/); the free tier is non-commercial only
- [ipwho.is](https://ipwhois.io)

The research design follows Anthropic's [multi-agent research system](https://www.anthropic.com/engineering/multi-agent-research-system) write-up.

The GPL and AGPL components are not vendored. eSpeak NG and phonemizer are installed as dependencies, and degoog/SearXNG run as separate services. Check their terms before redistributing a bundled build.

## License

No license has been chosen yet. Until a `LICENSE` file is added, all rights are reserved.
