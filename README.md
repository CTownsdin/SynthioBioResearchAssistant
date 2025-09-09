# myResearchAssistant

Simple runbook for querying and serving GraphRAG from this repo.

## 0) From project root

```zsh
cd /Users/ctown/src/myResearchAssistant
```

## 1) Activate venv

```zsh
source .venv/bin/activate
```

## 2) GraphRAG CLI: view help

```zsh
graphrag query --help
```

## 3) GraphRAG CLI: basic sanity query

```zsh
graphrag query --method basic \
  -q "What diseases or therapies are discussed in the corpus?" \
  --config settings.yaml --root . -v
```

## 4) Python helper (global search)

```zsh
python query_runner.py --query "What diseases or therapies are discussed in the corpus?" --verbose
```

## 5) Start the Flask API

```zsh
# new terminal (or tab), then:
cd /Users/ctown/src/myResearchAssistant
source .venv/bin/activate

# first time only
pip install Flask

# optional: verbose GraphRAG query logs + permissive CORS for local UI
export GRAPHRAG_QUERY_VERBOSE=1
export CORS_ALLOW_ORIGIN='*'

# run server (http://127.0.0.1:5000)
python app.py
```

Smoke test (from another terminal):

```zsh
curl -s -X POST http://127.0.0.1:5000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"What diseases or therapies are discussed in the corpus?"}'
```

## 6) Start the React Vite UI

```zsh
# new terminal
cd /Users/ctown/src/myResearchAssistant/web
npm install

# optional: point UI to a custom API URL (defaults to http://127.0.0.1:5000)
# export VITE_API_URL=http://127.0.0.1:5000

npm run dev
```

---

Notes:
- Ensure `.env` contains `GRAPHRAG_API_KEY` and do not commit it.
- Indexing should be completed before querying (artifacts in `output/`).
