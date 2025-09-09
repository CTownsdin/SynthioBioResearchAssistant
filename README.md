# myResearchAssistant

########################
Run a graphRAG cli query
########################

From project root:

## activate venv and view graphrag cli options
$ source .venv/bin/activate && graphrag query --help

# use graphrag cli to do a local query
$ graphrag query --method basic -q "What diseases or therapies are discussed in the corpus?" --config settings.yaml --root . -v

# Use the query_runner.py
python query_runner.py --query "What diseases or therapies are discussed in the corpus?" --verbose


#########################
# Start the flask app api
#########################
# 1) New terminal window, then from project root:
cd /Users/ctown/src/myResearchAssistant

# 2) Activate venv
source .venv/bin/activate

# 3) Install Flask (first time only)
pip install Flask

# 4) Optional: verbose GraphRAG query logs + CORS for local React
export GRAPHRAG_QUERY_VERBOSE=1
export CORS_ALLOW_ORIGIN=*

# 5) Run the app (defaults to http://127.0.0.1:5000)
python app.py

# 6) Smoke test it in a new terminal
curl -s -X POST http://127.0.0.1:5000/query \
  -H 'Content-Type: application/json' \
  -d '{"question":"What diseases or therapies are discussed in the corpus?"}'


#########################
# Start the React Vite UI
#########################

# 1) New terminal, go to the web app
cd /Users/ctown/src/myResearchAssistant/web

# 2) Install deps (first time only)
npm install

# 3) Ensure API URL (defaults to http://127.0.0.1:5000; override if needed)
# For example, if your Flask runs elsewhere:
# export VITE_API_URL=http://127.0.0.1:5000

# 4) Start Vite dev server
npm run dev
