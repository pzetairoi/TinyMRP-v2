import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import type { ApiError } from '../lib/api'

type User = {
  id: string
  email: string
  roles?: string[]
}

type Token = {
  id: string
  label: string
  created_at?: string
  last_used_at?: string
  revoked_at?: string
}

type Scheme = {
  id: string
  name: string
  is_preset?: boolean
  is_recommended?: boolean
  visibility?: string
}

export default function AdminAddinPage() {
  const [users, setUsers] = useState<User[]>([])
  const [selectedUser, setSelectedUser] = useState<User | null>(null)
  const [tokens, setTokens] = useState<Token[]>([])
  const [schemes, setSchemes] = useState<Scheme[]>([])
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadUsers()
    loadSchemes()
  }, [])

  async function loadUsers() {
    setError(null)
    try {
      const resp = await apiFetch<{ users: User[] }>('/api/admin/users')
      setUsers(resp.users || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load users.')
    }
  }

  async function loadUserTokens(user: User) {
    setError(null)
    try {
      const resp = await apiFetch<{ tokens: Token[] }>(`/api/admin/users/${user.id}/tokens`)
      setSelectedUser(user)
      setTokens(resp.tokens || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load tokens.')
    }
  }

  async function revokeToken(userId: string, tokenId: string) {
    setError(null)
    setMessage(null)
    try {
      await apiFetch(`/api/admin/users/${userId}/tokens/${tokenId}`, { method: 'DELETE' })
      setMessage('Token revoked.')
      if (selectedUser) {
        loadUserTokens(selectedUser)
      }
    } catch (err) {
      setError((err as ApiError).message || 'Failed to revoke token.')
    }
  }

  async function loadSchemes() {
    setError(null)
    try {
      const resp = await apiFetch<{ schemes: Scheme[] }>('/api/numbering/schemes')
      setSchemes(resp.schemes || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load schemes.')
    }
  }

  async function updateScheme(scheme: Scheme) {
    setError(null)
    setMessage(null)
    try {
      await apiFetch(`/api/numbering/schemes/${scheme.id}`, {
        method: 'PUT',
        body: JSON.stringify({
          name: scheme.name,
          is_preset: scheme.is_preset,
          is_recommended: scheme.is_recommended,
          visibility: scheme.visibility,
        }),
      })
      setMessage('Scheme updated.')
    } catch (err) {
      setError((err as ApiError).message || 'Failed to update scheme.')
    }
  }

  return (
    <div className="p-3">
      <h3 className="mb-3">Add-in Admin</h3>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card p-3 mb-4">
        <h5>Users</h5>
        <div className="table-responsive">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Email</th>
                <th>Roles</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {users.map((user) => (
                <tr key={user.id}>
                  <td>{user.email}</td>
                  <td>{user.roles?.join(', ') || '-'}</td>
                  <td>
                    <button className="btn btn-sm btn-outline-secondary" onClick={() => loadUserTokens(user)}>
                      View tokens
                    </button>
                  </td>
                </tr>
              ))}
              {!users.length && (
                <tr>
                  <td colSpan={3} className="text-muted text-center">
                    No users.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {selectedUser && (
          <div className="mt-3">
            <h6>Tokens for {selectedUser.email}</h6>
            <div className="table-responsive">
              <table className="table table-sm">
                <thead>
                  <tr>
                    <th>Label</th>
                    <th>Created</th>
                    <th>Last used</th>
                    <th>Status</th>
                    <th />
                  </tr>
                </thead>
                <tbody>
                  {tokens.map((token) => (
                    <tr key={token.id}>
                      <td>{token.label || '(no label)'}</td>
                      <td>{token.created_at || '-'}</td>
                      <td>{token.last_used_at || '-'}</td>
                      <td>{token.revoked_at ? 'Revoked' : 'Active'}</td>
                      <td>
                        {!token.revoked_at && (
                          <button
                            className="btn btn-sm btn-outline-danger"
                            onClick={() => revokeToken(selectedUser.id, token.id)}
                          >
                            Revoke
                          </button>
                        )}
                      </td>
                    </tr>
                  ))}
                  {!tokens.length && (
                    <tr>
                      <td colSpan={5} className="text-muted text-center">
                        No tokens.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      <div className="card p-3">
        <h5>Scheme presets</h5>
        <div className="table-responsive">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Name</th>
                <th>Preset</th>
                <th>Recommended</th>
                <th>Visibility</th>
                <th />
              </tr>
            </thead>
            <tbody>
              {schemes.map((scheme, idx) => (
                <tr key={scheme.id}>
                  <td>{scheme.name}</td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!scheme.is_preset}
                      onChange={(e) => {
                        const next = [...schemes]
                        next[idx] = { ...scheme, is_preset: e.target.checked }
                        setSchemes(next)
                      }}
                    />
                  </td>
                  <td>
                    <input
                      type="checkbox"
                      checked={!!scheme.is_recommended}
                      onChange={(e) => {
                        const next = [...schemes]
                        next[idx] = { ...scheme, is_recommended: e.target.checked }
                        setSchemes(next)
                      }}
                    />
                  </td>
                  <td>
                    <select
                      className="form-select form-select-sm"
                      value={scheme.visibility || 'advanced_only'}
                      onChange={(e) => {
                        const next = [...schemes]
                        next[idx] = { ...scheme, visibility: e.target.value }
                        setSchemes(next)
                      }}
                    >
                      <option value="quickstart">quickstart</option>
                      <option value="advanced_only">advanced_only</option>
                    </select>
                  </td>
                  <td>
                    <button className="btn btn-sm btn-outline-primary" onClick={() => updateScheme(scheme)}>
                      Save
                    </button>
                  </td>
                </tr>
              ))}
              {!schemes.length && (
                <tr>
                  <td colSpan={5} className="text-muted text-center">
                    No schemes.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
