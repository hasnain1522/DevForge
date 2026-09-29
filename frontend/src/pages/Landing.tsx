import { Link } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

const workflow = [
  ['01', 'Analyze', 'Measure structure, tests, lint and documentation.'],
  ['02', 'Prioritize', 'Turn evidence into focused engineering missions.'],
  ['03', 'Execute', 'Run scoped agent work with visible checkpoints.'],
  ['04', 'Verify', 'Back every result with real tool output.'],
]

export default function Landing() {
  const { user, loading } = useAuth()
  return (
    <main className="devforge-shell devforge-grid min-h-screen bg-[#050914] text-white">
      <span className="devforge-orb one" /><span className="devforge-orb two" />
      <header className="relative z-10 mx-auto flex w-full max-w-7xl items-center justify-between px-6 py-6 lg:px-8">
        <Link to="/" className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl border border-cyan-300/30 bg-cyan-300 text-sm font-black text-slate-950 shadow-lg shadow-cyan-500/20">◆</span><span className="font-semibold tracking-[0.18em]">DEVFORGE</span></Link>
        {!loading && (user ? <Link to="/overview" className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-cyan-100 transition hover:border-cyan-300/30 hover:bg-cyan-300/10">Open workspace →</Link> : <Link to="/login" className="rounded-full border border-white/10 bg-white/5 px-4 py-2 text-sm text-slate-200 transition hover:border-cyan-300/30 hover:text-white">Log in</Link>)}
      </header>
      <section className="relative z-10 mx-auto grid w-full max-w-7xl items-center gap-14 px-6 pb-20 pt-12 lg:grid-cols-[1.08fr_.92fr] lg:px-8 lg:pb-28 lg:pt-20">
        <div className="devforge-reveal">
          <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-cyan-300/15 bg-cyan-300/5 px-3 py-1.5 text-[11px] font-semibold uppercase tracking-[0.2em] text-cyan-200"><span className="devforge-pulse h-2 w-2 rounded-full bg-cyan-300" />Agentic engineering control center</div>
          <h1 className="max-w-4xl text-5xl font-semibold leading-[1.03] tracking-[-0.04em] sm:text-6xl lg:text-7xl">From messy repository<span className="block bg-gradient-to-r from-cyan-200 via-white to-indigo-300 bg-clip-text text-transparent">to verified engineering work.</span></h1>
          <p className="mt-7 max-w-2xl text-base leading-8 text-slate-300 sm:text-lg">DevForge analyzes a repository, identifies engineering problems, creates prioritized missions, coordinates scoped agents, and verifies what actually changed.</p>
          <div className="mt-9 flex flex-wrap items-center gap-4"><Link to={user ? '/overview' : '/login'} className="group inline-flex items-center gap-3 rounded-xl bg-cyan-300 px-6 py-3.5 text-sm font-bold text-slate-950 shadow-xl shadow-cyan-500/15 transition hover:-translate-y-0.5 hover:bg-cyan-200">ENTER DEVFORGE <span className="transition-transform group-hover:translate-x-1">→</span></Link>{!user && <Link to="/register" className="text-sm text-slate-300 transition hover:text-white">Create workspace</Link>}</div>
          <div className="mt-12 flex flex-wrap gap-3 text-xs text-slate-400">{['Real pytest verification','Ruff evidence','Checkpoint-aware execution','Polished ZIP delivery'].map(item => <span key={item} className="rounded-full border border-white/10 bg-white/[.03] px-3 py-1.5">{item}</span>)}</div>
        </div>
        <div className="devforge-reveal devforge-reveal-delay-2">
          <div className="devforge-scan rounded-3xl border border-white/10 bg-slate-950/70 p-5 shadow-2xl shadow-slate-950/50 backdrop-blur-xl">
            <div className="flex items-center justify-between border-b border-white/10 pb-4"><div><p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-slate-500">LIVE PIPELINE</p><p className="mt-1 text-sm font-medium text-white">Repository → verified change</p></div><span className="rounded-full border border-emerald-300/20 bg-emerald-300/10 px-3 py-1 text-[10px] font-semibold uppercase tracking-wider text-emerald-300">evidence-led</span></div>
            <ol className="mt-5 space-y-2">{workflow.map(([step,title,description]) => <li key={step} className="devforge-card flex gap-4 rounded-2xl border border-white/5 bg-white/[.025] p-4"><span className="font-mono text-xs text-cyan-300">{step}</span><div className="min-w-0"><h2 className="text-sm font-semibold text-white">{title}</h2><p className="mt-1 text-xs leading-5 text-slate-400">{description}</p></div><span className="ml-auto mt-1 text-cyan-300/60">↗</span></li>)}</ol>
            <div className="mt-5 rounded-2xl border border-cyan-300/10 bg-black/30 p-4 font-mono text-xs"><p><span className="text-cyan-300">$</span> devforge analyze</p><p className="mt-2 text-slate-400">→ missions generated</p><p className="mt-1 text-slate-400">→ agents executing</p><p className="mt-1 text-emerald-300">→ verification passed / evidence recorded</p></div>
          </div>
        </div>
      </section>
      <section className="relative z-10 mx-auto grid w-full max-w-7xl gap-4 px-6 pb-20 sm:grid-cols-3 lg:px-8">{[['01','Observe','See the repository before touching it.'],['02','Engineer','Make scoped, mission-specific changes.'],['03','Prove','Keep the commands and outcomes behind the result.']].map(([n,title,body]) => <article key={n} className="devforge-card rounded-2xl border border-white/10 bg-white/[.035] p-5 backdrop-blur"><p className="font-mono text-xs text-cyan-300">{n}</p><h2 className="mt-3 font-semibold">{title}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{body}</p></article>)}</section>
      <footer className="relative z-10 border-t border-white/10 px-6 py-6 text-center text-xs text-slate-500">DevForge · AI Engineering Control Center</footer>
    </main>
  )
}
