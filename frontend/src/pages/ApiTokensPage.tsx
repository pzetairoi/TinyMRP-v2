import { useEffect, useState } from 'react'
import { apiFetch } from '../lib/api'
import type { ApiError } from '../lib/api'

type Token = {
  id: string
  label: string
  created_at?: string
  created_at_display?: string
  last_used_at?: string
  last_used_at_display?: string
  revoked_at?: string
  revoked_at_display?: string
  expires_at?: string
  expires_at_display?: string
}

export default function ApiTokensPage() {
  const [tokens, setTokens] = useState<Token[]>([])
  const [label, setLabel] = useState('')
  const [newToken, setNewToken] = useState('')
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadTokens()
  }, [])

  async function loadTokens() {
    setError(null)
    try {
      const resp = await apiFetch<{ tokens: Token[] }>('/api/me/tokens')
      setTokens(resp.tokens || [])
    } catch (err) {
      setError((err as ApiError).message || 'Failed to load tokens.')
    }
  }

  async function createToken() {
    setError(null)
    setMessage(null)
    try {
      const resp = await apiFetch<{ token: string }>('/api/me/tokens', {
        method: 'POST',
        body: JSON.stringify({ label }),
      })
      setNewToken(resp.token)
      setLabel('')
      setMessage('Token created. Copy it now; it will not be shown again.')
      loadTokens()
    } catch (err) {
      setError((err as ApiError).message || 'Failed to create token.')
    }
  }

  async function revokeToken(id: string) {
    setError(null)
    setMessage(null)
    try {
      await apiFetch(`/api/me/tokens/${id}`, { method: 'DELETE' })
      setMessage('Token revoked.')
      loadTokens()
    } catch (err) {
      setError((err as ApiError).message || 'Failed to revoke token.')
    }
  }

  function renderTokenDate(display?: string, fallback?: string) {
    return display || fallback || '-'
  }

  return (
    <div className="p-3">
      <h3 className="mb-3">My API Tokens</h3>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card p-3 mb-3">
        <label className="form-label">New token label</label>
        <div className="d-flex gap-2">
          <input className="form-control" value={label} onChange={(e) => setLabel(e.target.value)} />
          <button className="btn btn-primary" onClick={createToken}>
            Create
          </button>
        </div>
        {newToken && (
          <div className="alert alert-warning mt-3">
            <div className="mb-2">Copy this token now:</div>
            <div className="d-flex gap-2">
              <input className="form-control" value={newToken} readOnly />
              <button
                className="btn btn-outline-secondary"
                onClick={() => navigator.clipboard.writeText(newToken)}
              >
                Copy
              </button>
            </div>
          </div>
        )}
      </div>

      <div className="card p-3">
        <h5>Active tokens</h5>
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
                  <td>{renderTokenDate(token.created_at_display, token.created_at)}</td>
                  <td>{renderTokenDate(token.last_used_at_display, token.last_used_at)}</td>
                  <td>{token.revoked_at ? 'Revoked' : 'Active'}</td>
                  <td>
                    {!token.revoked_at && (
                      <button className="btn btn-sm btn-outline-danger" onClick={() => revokeToken(token.id)}>
                        Revoke
                      </button>
                    )}
                  </td>
                </tr>
              ))}
              {!tokens.length && (
                <tr>
                  <td colSpan={5} className="text-muted text-center">
                    No tokens yet.
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
