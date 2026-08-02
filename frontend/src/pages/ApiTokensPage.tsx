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
  status?: 'active' | 'revoked' | 'expired' | 'legacy_no_expiry'
  is_active?: boolean
  legacy_no_expiry?: boolean
  revocation_reason?: string
}

type TokenPolicy = {
  default_ttl_days: number
  max_ttl_days: number
}

export default function ApiTokensPage() {
  const [tokens, setTokens] = useState<Token[]>([])
  const [label, setLabel] = useState('')
  const [newToken, setNewToken] = useState('')
  const [lifetimeDays, setLifetimeDays] = useState<number | null>(null)
  const [policy, setPolicy] = useState<TokenPolicy>({ default_ttl_days: 90, max_ttl_days: 365 })
  const [message, setMessage] = useState<string | null>(null)
  const [error, setError] = useState<string | null>(null)

  useEffect(() => {
    loadTokens()
  }, [])

  async function loadTokens() {
    setError(null)
    try {
      const resp = await apiFetch<{ tokens: Token[]; policy?: TokenPolicy }>('/api/me/tokens')
      setTokens(resp.tokens || [])
      if (resp.policy) {
        setPolicy(resp.policy)
        setLifetimeDays((current) => current ?? resp.policy?.default_ttl_days ?? 90)
      }
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
        body: JSON.stringify({ label, expires_in_days: lifetimeDays ?? policy.default_ttl_days }),
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
    if (!window.confirm('Revoke this token now? Connected clients using it will stop working.')) return
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

  async function rotateToken(id: string) {
    if (!window.confirm('Rotate this token? The existing secret will stop working immediately.')) return
    setError(null)
    setMessage(null)
    try {
      const resp = await apiFetch<{ token: string }>(`/api/me/tokens/${id}/rotate`, {
        method: 'POST',
        body: JSON.stringify({ expires_in_days: lifetimeDays ?? policy.default_ttl_days }),
      })
      setNewToken(resp.token)
      setMessage('Token rotated. Replace the old secret now; this replacement is shown only once.')
      await loadTokens()
    } catch (err) {
      setError((err as ApiError).message || 'Failed to rotate token.')
    }
  }

  function renderTokenDate(display?: string, fallback?: string) {
    return display || fallback || '-'
  }

  function statusLabel(token: Token) {
    if (token.status === 'legacy_no_expiry') return 'Legacy · no expiry'
    if (token.status === 'expired') return 'Expired'
    if (token.status === 'revoked') return 'Revoked'
    return 'Active'
  }

  return (
    <div className="p-3">
      <h3 className="mb-3">My API Tokens</h3>
      {message && <div className="alert alert-success">{message}</div>}
      {error && <div className="alert alert-danger">{error}</div>}

      <div className="card p-3 mb-3">
        <p className="text-muted mb-3">
          Tokens expire automatically. Rotation revokes the old token immediately, so update the connected client before closing this page.
        </p>
        <div className="row g-3 align-items-end">
          <div className="col-md-8">
            <label className="form-label" htmlFor="tokenLabel">New token label</label>
            <input id="tokenLabel" className="form-control" maxLength={120} value={label} onChange={(e) => setLabel(e.target.value)} />
          </div>
          <div className="col-md-2">
            <label className="form-label" htmlFor="tokenLifetime">Lifetime (days)</label>
            <input
              id="tokenLifetime"
              className="form-control"
              type="number"
              min={1}
              max={policy.max_ttl_days}
              value={lifetimeDays ?? policy.default_ttl_days}
              onChange={(e) => setLifetimeDays(Number(e.target.value))}
            />
          </div>
          <div className="col-md-2 d-grid">
            <button className="btn btn-primary" onClick={createToken}>
            Create
            </button>
          </div>
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
        <h5>Token history</h5>
        <div className="table-responsive">
          <table className="table table-sm">
            <thead>
              <tr>
                <th>Label</th>
                <th>Created</th>
                <th>Last used</th>
                <th>Expires</th>
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
                  <td>{token.legacy_no_expiry ? 'No expiry' : renderTokenDate(token.expires_at_display, token.expires_at)}</td>
                  <td>{statusLabel(token)}</td>
                  <td>
                    {token.is_active && (
                      <div className="d-flex gap-2">
                        <button className="btn btn-sm btn-outline-primary" onClick={() => rotateToken(token.id)}>
                          Rotate
                        </button>
                        <button className="btn btn-sm btn-outline-danger" onClick={() => revokeToken(token.id)}>
                          Revoke
                        </button>
                      </div>
                    )}
                  </td>
                </tr>
              ))}
              {!tokens.length && (
                <tr>
                  <td colSpan={6} className="text-muted text-center">
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
