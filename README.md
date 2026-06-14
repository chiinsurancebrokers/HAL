# HAL v2.0 — Railway Edition

> **HAL** — Heuristically Programmed Algorithmic Layer  
> Personal AI operating system for Christos Iatropoulos · Ashlar Insurance

## Architecture: HAL is the Brain

HAL v2 inverts the old structure. Previously HAL was one tab among sixteen.  
Now **HAL is the brain** — the default screen, the first thing you see.  
Everything else (Quote Engine, Communications, Renewals) is a subsidiary tool.

### What's new

| Feature | Description |
|---------|-------------|
| **Universal Upload** | Drop PDFs, images, Word, Excel, CSV into HAL. It reads everything. |
| **ChatGPT Second Opinion** | Optional 🤖 button under every HAL answer. Advisory only. |
| **Brain-first navigation** | HAL Chat is always the default. Tools are one click away. |
| **Railway deployment** | Procfile + railway.toml ready. |

---

## Deploy to Railway

### 1. Push to GitHub

```bash
git init
git add .
git commit -m "HAL v2.0 — brain-first architecture"
git remote add origin https://github.com/YOUR-ORG/hal-railway.git
git push -u origin main
```

### 2. Create Railway project

1. Go to [railway.app](https://railway.app) → New Project → Deploy from GitHub repo
2. Select the repo
3. Railway auto-detects the `Procfile`

### 3. Add environment variables

In Railway dashboard → Variables, add:

```
Claude_API_Key = sk-ant-api03-...
HAL_PIN = <sha256-hash-of-your-pin>
OPENAI_API_KEY = sk-...          # optional — enables ChatGPT second opinion
```

Generate your PIN hash:
```bash
python3 -c "import hashlib; print(hashlib.sha256('YOUR-PIN'.encode()).hexdigest())"
```

### 4. Deploy

Railway builds and deploys automatically on push. Your app will be at:
`https://your-project.up.railway.app`

---

## Local Development

```bash
pip install -r requirements.txt
cp .streamlit/secrets.toml.template .streamlit/secrets.toml
# Edit secrets.toml with your keys
streamlit run app.py
```

---

## Project Structure

```
hal-railway/
├── app.py              # Main app — HAL brain + subsidiary tools
├── hal_brain.py         # Universal file processor + ChatGPT second opinion
├── rate_tables.py       # 2025 carrier rate tables (Morgan Price, April, IMG)
├── extraction.py        # PDF → Claude → structured JSON extraction
├── analysis.py          # AI-powered recommendation narrative
├── pptx_builder.py      # PowerPoint quote presentation builder
├── config.py            # Colors, model settings, broker defaults
├── requirements.txt     # Python dependencies
├── Procfile             # Railway start command
├── railway.toml         # Railway build config
├── .streamlit/
│   ├── config.toml      # Streamlit theme (Ashlar brand)
│   └── secrets.toml.template
└── brochures/           # Carrier brochure PDFs
```

---

## Your 3 Quotes Workflow

The reason for this rebuild: **you have 3 quotes for a female 44 Greek living in Belgium and couldn't upload them.**

Now:
1. Open HAL (it's the default screen)
2. Click "📎 Upload files" → drop all 3 PDFs
3. Type: "Compare these 3 quotes for a 44-year-old Greek female living in Belgium"
4. HAL reads all 3, compares them, recommends
5. Click 🤖 under the answer for a ChatGPT cross-check if you want

---

*Confidential — Christos Iatropoulos | Ashlar Insurance | v2.0 June 2026*
