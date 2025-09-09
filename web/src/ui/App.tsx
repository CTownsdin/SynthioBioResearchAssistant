import React, { useMemo, useState } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'

const API_URL = import.meta.env.VITE_API_URL ?? 'http://127.0.0.1:5000'

async function ask(question: string) {
  const res = await fetch(`${API_URL}/query`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ question }),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`HTTP ${res.status}: ${text}`)
  }
  return res.json() as Promise<{
    answer: string
    citations: Array<{ id: string; title?: string; rank?: number }>
    run_dir?: string
  }>
}

export default function App() {
  const [q, setQ] = useState('What diseases or therapies are discussed in the corpus?')
  const [loading, setLoading] = useState(false)
  const [answer, setAnswer] = useState<string>('')
  const [citations, setCitations] = useState<Array<{ id: string; title?: string; rank?: number }>>([])
  const [error, setError] = useState<string>('')

  const onSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setLoading(true)
    setError('')
    setAnswer('')
    setCitations([])
    try {
      const data = await ask(q)
      setAnswer(data.answer)
      setCitations(data.citations || [])
    } catch (err: any) {
      setError(err?.message ?? String(err))
    } finally {
      setLoading(false)
    }
  }

  const placeholder = useMemo(
    () => 'Ask a question about the indexed corpus…',
    []
  )

  return (
    <div className={"min-h-dvh bg-app-gradient text-gray-900 dark:text-slate-100"}>
      <header className="border-b border-white/10 bg-white/70 backdrop-blur dark:bg-slate-900/60">
        <div className="mx-auto max-w-4xl px-4 py-4 flex items-center justify-between">
          <h1 className="text-xl font-semibold bg-gradient-to-r from-brand-600 via-pink-500 to-emerald-500 bg-clip-text text-transparent">GraphRAG Researcher</h1>
          <span className="text-xs text-gray-500">API: {API_URL}</span>
        </div>
      </header>

      <main className="mx-auto max-w-4xl px-4 py-6">
        <form onSubmit={onSubmit} className="flex gap-3">
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder={placeholder}
            className="flex-1 rounded-md border border-gray-300 bg-white/90 px-3 py-2 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200 dark:bg-slate-900/60 dark:border-slate-700 dark:focus:ring-brand-500"
          />
          <button
            type="submit"
            disabled={loading}
            className="inline-flex items-center justify-center rounded-md bg-gradient-to-r from-brand-600 via-pink-600 to-emerald-600 px-4 py-2 text-white shadow hover:from-brand-700 hover:via-pink-700 hover:to-emerald-700 disabled:opacity-60"
          >
            {loading && (
              <svg className="mr-2 h-4 w-4 animate-spin" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4"></circle>
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v4a4 4 0 00-4 4H4z"></path>
              </svg>
            )}
            {loading ? 'Asking…' : 'Ask'}
          </button>
        </form>

        {error && (
          <div className="mt-4 rounded-md border border-red-200 bg-red-50 p-3 text-red-700">
            {error}
          </div>
        )}

        {!answer && !loading && !error && (
          <div className="mt-8 rounded-md border border-dashed border-gray-300 p-6 text-sm text-gray-600">
            Your answer will appear here. Try asking about diseases, therapies, entities, or relationships.
          </div>
        )}

        {answer && (
          <section className="mt-6 grid grid-cols-1 gap-6 md:grid-cols-3">
            <div className="md:col-span-2 rounded-md border border-white/20 bg-white/80 p-5 shadow backdrop-blur dark:bg-slate-900/60 dark:border-slate-700">
              <h2 className="mb-3 text-lg font-semibold">Answer</h2>
              <div className="markdown prose prose-sm max-w-none dark:prose-invert">
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
              </div>
            </div>

            <aside className="rounded-md border border-white/20 bg-white/80 p-5 shadow backdrop-blur dark:bg-slate-900/60 dark:border-slate-700">
              <h3 className="mb-3 text-base font-semibold">Citations</h3>
              {citations.length === 0 ? (
                <p className="text-sm text-gray-500">No citations provided.</p>
              ) : (
                <ul className="space-y-2 text-sm">
                  {citations.map((c) => (
                    <li key={c.id} className="rounded border border-gray-200/60 p-3 hover:bg-white/70 dark:hover:bg-slate-800/60">
                      <div className="font-medium">{c.title || `Report ${c.id}`}</div>
                      {typeof c.rank !== 'undefined' && (
                        <div className="text-xs text-gray-500">rank {c.rank}</div>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </aside>
          </section>
        )}
      </main>

      <footer className="mt-10 border-t border-white/10 bg-white/60 backdrop-blur dark:bg-slate-900/60">
        <div className="mx-auto max-w-4xl px-4 py-4 text-xs text-gray-600 dark:text-slate-400">
          Built with Vite + React + Tailwind
        </div>
      </footer>
    </div>
  )
}
