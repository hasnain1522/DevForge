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
    event.preventDefault()
    setBusy(true)
    setError(null)
    try {
      if (isRegister) await register(email, password)
      else await login(email, password)
      navigate('/overview', { replace: true })
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Authentication failed')
    } finally {
      setBusy(false)
    }
  }

  return (
    <main className="min-h-screen bg-slate-950 text-white grid lg:grid-cols-2">
      <section className="hidden lg:flex flex-col justify-between bg-[#0b1220] p-12 xl:p-16">
        <Link to="/" className="flex items-center gap-3"><span className="h-9 w-9 rounded-lg bg-cyan-400 text-slate-950 grid place-items-center font-black">D</span><span className="font-semibold tracking-wide">DEVFORGE</span></Link>
        <div className="max-w-lg"><p className="text-xs font-semibold tracking-[0.2em] text-cyan-300">ENGINEERING CONTROL CENTER</p><h1 className="mt-5 text-4xl font-semibold leading-tight">Your repositories. Your missions. Your evidence.</h1><p className="mt-5 text-slate-400 leading-7">Sign in to analyze code, run scoped engineering work, and review results backed by actual verification.</p></div>
        <p className="text-xs text-slate-500">Local-first workspace · Provider credentials remain on the backend</p>
      </section>
      <section className="flex items-center justify-center px-6 py-12">
        <div className="w-full max-w-md">
          <Link to="/" className="text-sm text-cyan-300 hover:text-cyan-200 lg:hidden">← DevForge</Link>
          <p className="mt-8 text-xs font-semibold tracking-[0.2em] text-cyan-300 uppercase">{isRegister ? 'Create workspace account' : 'Welcome back'}</p>
          <h2 className="mt-3 text-3xl font-semibold">{isRegister ? 'Create your account' : 'Log in to DevForge'}</h2>
          <p className="mt-2 text-sm text-slate-400">{isRegister ? 'Your repository data is isolated to your account.' : 'Continue to your engineering workspace.'}</p>
          <form className="mt-8 space-y-5" onSubmit={submit}>
            <label className="block text-sm font-medium text-slate-200">Email
              <input required type="email" autoComplete="email" value={email} onChange={e => setEmail(e.target.value)} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-white outline-none focus:border-cyan-300" />
            </label>
            <label className="block text-sm font-medium text-slate-200">Password
              <input required type="password" minLength={12} maxLength={128} autoComplete={isRegister ? 'new-password' : 'current-password'} value={password} onChange={e => setPassword(e.target.value)} className="mt-2 w-full rounded-md border border-slate-700 bg-slate-900 px-3 py-2.5 text-white outline-none focus:border-cyan-300" />
              {isRegister && <span className="mt-1 block text-xs text-slate-500">Use at least 12 characters.</span>}
            </label>
            {error && <p role="alert" className="rounded-md border border-red-900 bg-red-950/50 px-3 py-2 text-sm text-red-200">{error}</p>}
            <button disabled={busy} className="w-full rounded-md bg-cyan-300 px-4 py-3 text-sm font-bold text-slate-950 hover:bg-cyan-200 disabled:opacity-60">{busy ? 'Please wait…' : isRegister ? 'Create account' : 'Log in'}</button>
          </form>
          <p className="mt-6 text-sm text-slate-400">{isRegister ? 'Already have an account?' : 'New to DevForge?'}{' '}
            <Link to={isRegister ? '/login' : '/register'} className="font-medium text-cyan-300 hover:text-cyan-200">{isRegister ? 'Log in' : 'Register'}</Link>
          </p>
          <p className="mt-8 text-xs leading-5 text-slate-500">Sessions use an HttpOnly cookie. Passwords are hashed on the server; model provider keys never reach this page.</p>
        </div>
      </section>
    </main>
  )
}
