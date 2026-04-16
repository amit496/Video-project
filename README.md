# Automated World News → Indian Voice Video → YouTube

This repo creates a **~15 minute** world news style video:
RSS headlines → script → Indian voice (Edge TTS) → MP4 (anchor + B-roll) → thumbnail → optional YouTube upload.

The instructions below are **cell-wise (Colab/Notebook style)**: run one block at a time, top to bottom.

---

## Cells (run top to bottom)

### Cell 0 — Requirements

- Python **3.10+**
- **FFmpeg** installed and available in PATH

```bash
ffmpeg -version
python --version
```

### Cell 1 — Create & activate venv (recommended)

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
```

### Cell 2 — Install dependencies

```bash
pip install -r requirements.txt
```

### Cell 3 — Put required assets in place

- **Anchor image (required)**: put at least one file in `assets/anchor/` (png/jpg/webp)
- **Daily B-roll (optional)**: put files in `assets/news_today/` named in order: `01.jpg`, `02.mp4`, ...
- **Background music (optional)**: put tracks in `assets/news_music/`

See `assets/README_ASSETS.txt` for the daily folder workflow.

### Cell 4 — Configure `.env` (modes + keys)

Create `.env` and set only what you need.

- **Script provider**: `SCRIPT_PROVIDER=template` (no API), or `openai`, or `gemini`
- **B-roll source**: `BROLL_SOURCE=localai|runway|article|generated|openai|local`
- **SEO metadata**: set `SEO_METADATA_USE_LLM=0` if you don’t want LLM metadata

Minimal `.env` (offline script + local visuals):

```bash
cat > .env <<'EOF'
SCRIPT_PROVIDER=template
BROLL_SOURCE=localai
SEO_METADATA_USE_LLM=0
EOF
```

If you use OpenAI/Gemini, add keys (do **not** commit `.env`):

```bash
# OPENAI_API_KEY=...
# GEMINI_API_KEY=...
```

### Cell 5 — Preflight check

Preflight validates: ffmpeg, anchor image exists, and required keys for chosen modes.

```bash
python -m src.main --preflight
```

### Cell 6 — Dry run (only fetch RSS)

```bash
python -m src.main --dry-run
```

### Cell 7 — Render video (skip upload)

```bash
python -m src.main --skip-upload
```

Outputs:
- video: `output/news_<timestamp>.mp4`
- run artifacts: `temp/<timestamp>/` (script, voice.mp3, thumbnail.jpg, staged media)

### Cell 8 — YouTube upload (optional)

1) Create Google Cloud OAuth **Desktop app** credential  
2) Download JSON and save to `secrets/client_secret.json` (this folder is ignored by git)

Then run:

```bash
python -m src.main --privacy unlisted
```

---

## Colab (direct GitHub, no Drive)

Colab runs in a temporary VM at `/content`. You can clone from GitHub and run everything there **without** mounting Google Drive.

### Colab Cell A — Clone repo

```bash
rm -rf /content/Video-project
git clone https://github.com/amit496/Video-project.git /content/Video-project
cd /content/Video-project
```

### Colab Cell B — Install FFmpeg + Python deps

```bash
apt-get update -y
apt-get install -y ffmpeg
python -m pip install -r requirements.txt
```

### Colab Cell C — Add assets in Colab

Upload files into these folders (left sidebar → Files → Upload), or `wget/curl` them from your own URLs:

- `assets/anchor/` (required)
- `assets/news_today/` (optional)
- `assets/news_music/` (optional)

### Colab Cell D — Create `.env` (no Drive)

```bash
cat > .env <<'EOF'
SCRIPT_PROVIDER=template
BROLL_SOURCE=localai
SEO_METADATA_USE_LLM=0
EOF
```

If needed, set keys in the notebook **runtime** (recommended) instead of writing them to disk:

```bash
export OPENAI_API_KEY="..."
export GEMINI_API_KEY="..."
export RUNWAY_API_KEY="..."
```

### Colab Cell E — Run (render only)

```bash
python -m src.main --preflight
python -m src.main --skip-upload
ls -la output temp
```

### (Optional) Colab → push changes back to GitHub

Only do this if you intentionally created/edited files in the repo (e.g. updated README, configs).  
Never commit secrets (`.env`, `secrets/`, tokens).

```bash
git status
git add -A
git commit -m "Update from Colab"
git push
```

If `git push` asks for credentials in Colab, use a **GitHub Personal Access Token (PAT)**:

```bash
git remote set-url origin https://<YOUR_GITHUB_USERNAME>:<YOUR_GITHUB_PAT>@github.com/amit496/Video-project.git
git push
```

## Project layout (quick map)

- `src/main.py`: orchestration
- `src/config.py`: `.env` config
- `src/news_fetcher.py`: RSS collection
- `src/script_generator.py`: OpenAI/Gemini/template script
- `src/tts_edge.py`: Edge TTS voice
- `src/video_compose.py`: MoviePy composition (anchor corner + B-roll)
- `src/thumbnail_gen.py`: thumbnail
- `src/youtube_upload.py`: YouTube upload
- `src/preflight.py`: preflight checks

---

## Notes / expectations

- “100% copyright-free” cannot be guaranteed for scraped media. Prefer licensed/owned/AI-generated media.
- Talking/lip-synced anchor from a single photo usually needs GPU workflows (Wav2Lip/SadTalker) or paid APIs.
