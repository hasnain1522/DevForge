import { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth } from '../auth/AuthContext'

export default function AuthPage({ mode }: { mode: 'login' | 'register' }) {
  const isRegister = mode === 'register'
  const { login, register } = useAuth()
  const navigate = useNavigate()
  const [email, setEmail] = useState('')
  const [password, setPassword] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function submit(event: React.FormEvent<HTMLFormElement>) {
    event.preventDefault(); setBusy(true); setError(null)
    try { if (isRegister) await register(email, password); else await login(email, password); navigate('/overview', { replace: true }) }
    catch (err) { setError(err instanceof Error ? err.message : 'Authentication failed') }
    finally { setBusy(false) }
  }

  return (
    <main className="devforge-shell devforge-grid min-h-screen bg-[#050914] text-white">
      <span className="devforge-orb one" /><span className="devforge-orb two" />
      <div className="relative z-10 mx-auto grid min-h-screen w-full max-w-7xl lg:grid-cols-[1.05fr_.95fr]">
        <section className="hidden flex-col justify-between border-r border-white/10 p-10 lg:flex xl:p-16">
          <Link to="/" className="flex items-center gap-3"><span className="grid h-10 w-10 place-items-center rounded-xl bg-cyan-300 font-black text-slate-950">◆</span><span className="font-semibold tracking-[0.18em]">DEVFORGE</span></Link>
          <div className="max-w-xl"><p className="text-xs font-semibold uppercase tracking-[0.22em] text-cyan-300">ENGINEERING CONTROL CENTER</p><h1 className="mt-5 text-5xl font-semibold leading-tight tracking-[-0.03em]">Build with agents. <span className="text-cyan-200">Prove with evidence.</span></h1><p className="mt-6 max-w-lg leading-8 text-slate-400">Analyze repositories, turn findings into missions, execute focused changes, and inspect the verification trail from one workspace.</p></div>
          <div className="flex gap-2 text-xs text-slate-500"><span className="rounded-full border border-white/10 px-3 py-1">pytest</span><span className="rounded-full border border-white/10 px-3 py-1">ruff</span><span className="rounded-full border border-white/10 px-3 py-1">SSE</span><span className="rounded-full border border-white/10 px-3 py-1">agent orchestration</span></div>
        </section>
        <section className="flex items-center justify-center px-6 py-12 sm:px-10">
          <div className="devforge-reveal w-full max-w-md rounded-3xl border border-white/10 bg-slate-950/75 p-7 shadow-2xl backdrop-blur-xl sm:p-9">
            <Link to="/" className="text-sm text-cyan-300 lg:hidden">← DevForge</Link>
            <div className="mt-7"><p className="text-xs font-semibold uppercase tracking-[0.2em] text-cyan-300">{isRegister ? 'Create workspace account' : 'Welcome back'}</p><h2 className="mt-3 text-3xl font-semibold tracking-tight">{isRegister ? 'Start your control center.' : 'Enter DevForge.'}</h2><p className="mt-2 text-sm leading-6 text-slate-400">{isRegister ? 'Your repositories and execution history stay scoped to your account.' : 'Your engineering workspace is ready.'}</p></div>
            <form className="mt-8 space-y-5" onSubmit={submit}>
              <label className="block text-sm font-medium text-slate-200">Email<input required type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-white/[.04] px-4 py-3 text-white outline-none transition focus:border-cyan-300/60 focus:bg-white/[.06] focus:ring-4 focus:ring-cyan-300/5" /></label>
              <label className="block text-sm font-medium text-slate-200">Password<input required type="password" minLength={12} maxLength={128} autoComplete={isRegister ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} className="mt-2 w-full rounded-xl border border-white/10 bg-white/[.04] px-4 py-3 text-white outline-none transition focus:border-cyan-300/60 focus:bg-white/[.06] focus:ring-4 focus:ring-cyan-300/5" />{isRegister && <span className="mt-1 block text-xs text-slate-500">Use at least 12 characters.</span>}</label>
              {error && <p role="alert" className="rounded-xl border border-rose-400/20 bg-rose-400/10 px-4 py-3 text-sm text-rose-200">{error}</p>}
              <button disabled={busy} className="w-full rounded-xl bg-cyan-300 px-4 py-3.5 text-sm font-bold text-slate-950 shadow-lg shadow-cyan-500/10 transition hover:-translate-y-0.5 hover:bg-cyan-200 disabled:cursor-wait disabled:opacity-60">{busy ? 'Connecting…' : isRegister ? 'Create account →' : 'Log in →'}</button>
            </form>
            <p className="mt-6 text-sm text-slate-400">{isRegister ? 'Already have an account?' : 'New to DevForge?'}{' '}<Link to={isRegister ? '/login' : '/register'} className="font-medium text-cyan-300 hover:text-cyan-200">{isRegister ? 'Log in' : 'Register'}</Link></p>
            <p className="mt-8 border-t border-white/10 pt-5 text-xs leading-5 text-slate-600">Sessions use an HttpOnly cookie. Provider keys never reach the browser.</p>
          </div>
        </section>
      </div>
    </main>
  )
}
