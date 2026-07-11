// frontend/src/components/markups/MarkupThreadsPanel.tsx
import { useMemo, useState } from 'react'
import type { MarkupIdentityProfile, MarkupThread, MarkupThreadPriority } from './types'

type StatusFilter = 'open' | 'resolved' | 'all'

type Props = {
  threads: MarkupThread[]
  canEdit: boolean
  selectedObjectIds: string[]
  busy: boolean
  loading?: boolean
  error?: string | null
  onCreateThread: (input: {
    object_ids: string[]
    title: string
    priority: MarkupThreadPriority
    message: string
  }) => Promise<boolean>
  onReply: (threadId: string, text: string) => Promise<boolean>
  onSetStatus: (threadId: string, action: 'resolve' | 'reopen') => Promise<boolean>
  onViewThread: (thread: MarkupThread) => void
}

function initialsFor(label: string): string {
  const tokens = String(label || '').trim().split(/[\s._-]+/).filter(Boolean)
  if (!tokens.length) return 'U'
  if (tokens.length === 1) return tokens[0].slice(0, 2).toUpperCase()
  return `${tokens[0][0]}${tokens[1][0]}`.toUpperCase()
}

function markupAvatar(profile?: MarkupIdentityProfile | null, fallback = '') {
  const label = String(profile?.label || profile?.display_name || profile?.email || fallback || 'User').trim() || 'User'
  const shape = String(profile?.avatar_shape || 'circle').toLowerCase()
  const avatarClass = shape === 'square' ? 'square' : shape === 'rounded' ? 'rounded' : 'circle'
  return (
    <span
      className={`pd-identity-avatar pd-identity-avatar--sm pd-identity-avatar--${avatarClass}`}
      style={{ backgroundColor: String(profile?.avatar_color || '#1d4ed8') }}
      title={label}
      aria-hidden="true"
    >
      {String(profile?.initials || initialsFor(label)).slice(0, 2)}
    </span>
  )
}

function priorityBadge(priority: MarkupThreadPriority) {
  const cls = priority === 'high' ? 'text-bg-danger' : priority === 'low' ? 'text-bg-secondary' : 'text-bg-info'
  return <span className={`badge ${cls} pd-markup-priority`}>{priority}</span>
}

function statusBadge(status: 'open' | 'resolved') {
  return (
    <span className={`badge ${status === 'open' ? 'text-bg-warning' : 'text-bg-success'}`}>
      {status}
    </span>
  )
}

export default function MarkupThreadsPanel({
  threads,
  canEdit,
  selectedObjectIds,
  busy,
  loading,
  error,
  onCreateThread,
  onReply,
  onSetStatus,
  onViewThread,
}: Props) {
  const [filter, setFilter] = useState<StatusFilter>('open')
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<MarkupThreadPriority>('normal')
  const [message, setMessage] = useState('')
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({})

  const openCount = useMemo(() => threads.filter((t) => t.status === 'open').length, [threads])
  const visible = useMemo(() => {
    if (filter === 'all') return threads
    return threads.filter((t) => t.status === filter)
  }, [threads, filter])

  async function submitThread() {
    const text = message.trim()
    if (!text || !selectedObjectIds.length) return
    const ok = await onCreateThread({
      object_ids: selectedObjectIds,
      title: title.trim(),
      priority,
      message: text,
    })
    if (ok) {
      setCreating(false)
      setTitle('')
      setPriority('normal')
      setMessage('')
    }
  }

  async function submitReply(threadId: string) {
    const text = (replyDrafts[threadId] || '').trim()
    if (!text) return
    const ok = await onReply(threadId, text)
    if (ok) setReplyDrafts((prev) => ({ ...prev, [threadId]: '' }))
  }

  return (
    <div className="pd-markup-panel pd-card">
      <div className="pd-markup-panel-head">
        <h6 className="mb-0 d-flex align-items-center gap-2">
          Review threads
          <span className="badge rounded-pill text-bg-secondary">{threads.length}</span>
          {openCount > 0 ? <span className="badge rounded-pill text-bg-warning">{openCount} open</span> : null}
        </h6>
        <div className="btn-group btn-group-sm" role="group" aria-label="Filter threads by status">
          {(['open', 'resolved', 'all'] as StatusFilter[]).map((value) => (
            <button
              key={value}
              type="button"
              className={`btn ${filter === value ? 'btn-secondary' : 'btn-outline-secondary'}`}
              onClick={() => setFilter(value)}
            >
              {value}
            </button>
          ))}
        </div>
      </div>

      {canEdit ? (
        <div className="pd-markup-newthread">
          {!creating ? (
            <>
              <button
                type="button"
                className="btn btn-sm btn-outline-primary"
                disabled={busy || !selectedObjectIds.length}
                onClick={() => setCreating(true)}
              >
                <i className="pi pi-comments me-1" aria-hidden="true" />
                Add review comment
                {selectedObjectIds.length ? ` (${selectedObjectIds.length} object${selectedObjectIds.length > 1 ? 's' : ''})` : ''}
              </button>
              {!selectedObjectIds.length ? (
                <div className="text-muted small mt-1">Select one or more markup objects on the drawing first.</div>
              ) : null}
            </>
          ) : (
            <div className="pd-markup-newthread-form border rounded p-2">
              <div className="small fw-semibold mb-1">
                New review thread ({selectedObjectIds.length} linked object{selectedObjectIds.length > 1 ? 's' : ''})
              </div>
              <input
                type="text"
                className="form-control form-control-sm mb-1"
                placeholder="Title (optional)"
                maxLength={200}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                aria-label="Thread title"
              />
              <select
                className="form-select form-select-sm mb-1"
                value={priority}
                onChange={(e) => setPriority(e.target.value as MarkupThreadPriority)}
                aria-label="Thread priority"
              >
                <option value="low">Low priority</option>
                <option value="normal">Normal priority</option>
                <option value="high">High priority</option>
              </select>
              <textarea
                className="form-control form-control-sm mb-1"
                rows={3}
                placeholder="Describe the issue or request..."
                value={message}
                onChange={(e) => setMessage(e.target.value)}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && message.trim() && !busy) {
                    e.preventDefault()
                    submitThread()
                  }
                }}
                aria-label="Initial message"
              />
              <div className="d-flex gap-2">
                <button
                  type="button"
                  className="btn btn-sm btn-primary"
                  disabled={busy || !message.trim() || !selectedObjectIds.length}
                  onClick={submitThread}
                >
                  {busy ? 'Saving...' : 'Create thread'}
                </button>
                <button type="button" className="btn btn-sm btn-outline-secondary" disabled={busy} onClick={() => setCreating(false)}>
                  Cancel
                </button>
              </div>
            </div>
          )}
        </div>
      ) : null}

      {error ? <div className="alert alert-danger py-1 px-2 small my-2">{error}</div> : null}

      <div className="pd-markup-threadlist">
        {loading ? (
          <div className="text-muted small">Loading review threads...</div>
        ) : visible.length === 0 ? (
          <div className="text-muted small pd-markup-empty">
            {threads.length === 0
              ? 'No review threads yet. Select a markup object and add the first review comment.'
              : `No ${filter} threads.`}
          </div>
        ) : (
          visible.map((thread) => (
            <div key={thread.id} className={`pd-markup-thread border rounded p-2 ${thread.status === 'resolved' ? 'pd-markup-thread--resolved' : ''}`}>
              <div className="pd-markup-thread-head">
                <div className="pd-markup-thread-title">
                  {priorityBadge(thread.priority)}
                  {statusBadge(thread.status)}
                  <span className="fw-semibold">{thread.title || thread.messages[0]?.text?.slice(0, 60) || 'Review thread'}</span>
                </div>
                <div className="pd-markup-thread-actions">
                  {thread.linked ? (
                    <button
                      type="button"
                      className="btn btn-sm btn-outline-secondary"
                      title="View on drawing"
                      onClick={() => onViewThread(thread)}
                    >
                      <i className="pi pi-eye me-1" aria-hidden="true" />
                      View
                    </button>
                  ) : (
                    <span className="badge text-bg-light border" title="The linked markup object was removed">
                      Markup no longer present
                    </span>
                  )}
                  {canEdit ? (
                    thread.status === 'open' ? (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-success"
                        disabled={busy}
                        onClick={() => onSetStatus(thread.id, 'resolve')}
                      >
                        Resolve
                      </button>
                    ) : (
                      <button
                        type="button"
                        className="btn btn-sm btn-outline-warning"
                        disabled={busy}
                        onClick={() => onSetStatus(thread.id, 'reopen')}
                      >
                        Reopen
                      </button>
                    )
                  ) : null}
                </div>
              </div>

              <div className="pd-markup-messages">
                {thread.messages.map((msg) => (
                  <div key={msg.id} className="pd-markup-message">
                    {markupAvatar(msg.author_profile, msg.author_display || msg.author)}
                    <div className="pd-markup-message-body">
                      <div className="small text-muted">
                        <span className="fw-semibold">{msg.author_display || msg.author || 'User'}</span>
                        {msg.ts ? <span title={msg.ts_local || msg.ts}> - {msg.ts_display || msg.ts}</span> : null}
                      </div>
                      <div className="small pd-markup-message-text">{msg.text}</div>
                    </div>
                  </div>
                ))}
              </div>

              {thread.status === 'resolved' && thread.resolved_at_display ? (
                <div className="text-muted small mt-1">
                  Resolved by {thread.resolved_by || 'unknown'} - {thread.resolved_at_display}
                </div>
              ) : null}

              {canEdit ? (
                <div className="input-group input-group-sm mt-2">
                  <textarea
                    className="form-control"
                    rows={1}
                    placeholder="Reply..."
                    value={replyDrafts[thread.id] || ''}
                    onChange={(e) => setReplyDrafts((prev) => ({ ...prev, [thread.id]: e.target.value }))}
                    onKeyDown={(e) => {
                      if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && (replyDrafts[thread.id] || '').trim() && !busy) {
                        e.preventDefault()
                        submitReply(thread.id)
                      }
                    }}
                    aria-label={`Reply to thread ${thread.title || thread.id}`}
                  />
                  <button
                    type="button"
                    className="btn btn-outline-primary"
                    disabled={busy || !(replyDrafts[thread.id] || '').trim()}
                    onClick={() => submitReply(thread.id)}
                  >
                    Reply
                  </button>
                </div>
              ) : null}
            </div>
          ))
        )}
      </div>
    </div>
  )
}
