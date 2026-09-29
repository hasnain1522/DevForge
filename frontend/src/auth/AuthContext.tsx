import { createContext, useContext, useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { getCurrentUser, login as apiLogin, logout as apiLogout, register as apiRegister } from '../api/client'
import type { AuthUser } from '../types'

interface AuthValue {
  user: AuthUser | null
  loading: boolean
  login: (email: string, password: string) => Promise<void>
  register: (email: string, password: string) => Promise<void>
  logout: () => Promise<void>
}

const AuthContext = createContext<AuthValue | null>(null)

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AuthUser | null>(null)
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    let active = true
    getCurrentUser().then(value => { if (active) setUser(value) })
      .catch(() => { if (active) setUser(null) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const value = useMemo<AuthValue>(() => ({
    user,
    loading,
    login: async (email, password) => setUser(await apiLogin(email, password)),
    register: async (email, password) => setUser(await apiRegister(email, password)),
    logout: async () => { try { await apiLogout() } finally { setUser(null) } },
  }), [user, loading])

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext)
  if (!value) throw new Error('useAuth must be used inside AuthProvider')
  return value
}
