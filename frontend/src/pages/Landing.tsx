import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function Landing() {
  const { user, loading } = useAuth()
  return (
    <main className="min-h-screen bg-[#0b1220] text-white flex flex-col">
      <header className="w-full max-w-7xl mx-auto px-6 py-7 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <span className="h-9 w-9 rounded-lg bg-cyan-400 text-slate-950 grid place-items-center font-black">D</span>
          <span className="font-semibold tracking-wide">DEVFORGE</span>
        </div>
        {!loading && (user ? <Link to="/overview" className="text-sm text-cyan-200 hover:text-white">Open workspace →</Link>
          : <Link to="/login" className="text-sm text-slate-300 hover:text-white">Log in</Link>)}
      </header>
      <section className="flex-1 w-full max-w-7xl mx-auto px-6 py-16 md:py-24 grid md:grid-cols-[1.15fr_0.85fr] gap-14 items-center">
        <div>
          <p className="text-xs font-semibold tracking-[0.24em] text-cyan-300 uppercase mb-5">Engineering, with evidence</p>
          <h1 className="max-w-3xl text-4xl sm:text-5xl lg:text-6xl font-semibold leading-tight tracking-tight">
            Turn repository issues into verified engineering work.
          </h1>
          <p className="mt-6 max-w-2xl text-lg leading-8 text-slate-300">
            DevForge analyzes Python repositories, prioritizes maintenance missions, coordinates focused agents, and records the tests and changes behind every result.
          </p>
          <div className="mt-9 flex flex-wrap items-center gap-5">
            <Link to={user ? '/overview' : '/login'} className="inline-flex items-center gap-3 rounded-md bg-cyan-300 px-6 py-3 text-sm font-bold tracking-wide text-slate-950 hover:bg-cyan-200">
              ENTER DEVFORGE <span aria-hidden="true">→</span>
            </Link>
            {!user && <Link to="/register" className="text-sm text-slate-300 hover:text-white">Create an account</Link>}
          </div>
        </div>
        <div className="rounded-xl border border-slate-700 bg-slate-900/70 p-6 shadow-2xl">
          <div className="flex items-center justify-between border-b border-slate-700 pb-4">
            <div><p className="text-xs text-slate-400">ENGINEERING WORKFLOW</p><p className="mt-1 font-medium">From repository to verified change</p></div>
            <span className="rounded-full bg-emerald-400/10 px-3 py-1 text-xs text-emerald-300">Evidence-led</span>
          </div>
          <ol className="mt-5 space-y-4">
            {[
              ['01', 'Analyze', 'Measure code, tests, lint, and documentation'],
              ['02', 'Prioritize', 'Turn observed issues into engineering missions'],
              ['03', 'Execute', 'Run scoped agent work with visible activity'],
              ['04', 'Verify', 'Capture pytest, ruff, and change evidence'],
            ].map(([step, title, description]) => <li key={step} className="flex gap-4">
              <span className="mt-0.5 text-xs font-mono text-cyan-300">{step}</span>
              <div><h2 className="text-sm font-semibold">{title}</h2><p className="mt-1 text-sm text-slate-400">{description}</p></div>
            </li>)}
          </ol>
          <div className="mt-6 rounded-md border border-slate-700 bg-slate-950 p-4 font-mono text-xs text-slate-300">
            <p><span className="text-cyan-300">$</span> analyze → mission → execute</p>
            <p className="mt-2 text-emerald-300">✓ verification is backed by real tool output</p>
          </div>
        </div>
      </section>
      <footer className="px-6 py-5 text-center text-xs text-slate-500">DevForge · Local-first engineering control center</footer>
    </main>
  )
}
