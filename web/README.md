# GraphRAG Web (Vite + React)

Minimal UI to query the Flask API.

## Setup

1) In a new terminal:

```bash
cd web
npm install
npm run dev
```

By default it serves on http://127.0.0.1:5173 and calls the API at http://127.0.0.1:5000.

To point at a different API URL:

```bash
VITE_API_URL=http://127.0.0.1:5000 npm run dev
```
