// frontend/src/components/markups/MarkupThreadsPanel.tsx
// Unified review panel: general part comments and drawing-markup review
// threads share one chronological list with consistent actions (reply,
// resolve/reopen, delete, importance, open/resolved/all filters).
import { useEffect, useMemo, useState } from 'react'
import MentionTextarea from '../MentionTextarea'
import type {
  MarkupIdentityProfile,
  MarkupThread,
  MarkupThreadPriority,
  PartCommentPriority,
  PartCommentRow,
} from './types'

type StatusFilter = 'open' | 'resolved' | 'all'

export type MarkupTextMatch = { id: string; text: string }

type ReviewListItem =
  | { kind: 'thread'; ts: string; thread: MarkupThread }
  | { kind: 'comment'; ts: string; comment: PartCommentRow }

type Props = {
  partNumber: string
  revision: string
  threads: MarkupThread[]
  comments: PartCommentRow[]
  /** Markup-thread operations possible (drawing/preview image present). */
  canEditThreads: boolean
  /** General comment operations possible. */
  canComment: boolean
  selectedObjectIds: string[]
  busy: boolean
  commentsBusy?: boolean
  loading?: boolean
  error?: string | null
  commentsError?: string | null
  /** Search text shared with the tab; filters comments and threads. */
  filterText?: string
  /** Markup text objects matching the search. */
  textMatches?: MarkupTextMatch[]
  /** Object ids of a just-drawn markup: auto-opens the review form. */
  promptObjectIds?: string[] | null
  /** Object ids currently hidden on the drawing, including resolved/manual hides. */
  hiddenObjectIds?: string[]
  onPromptDismiss?: () => void
  onCreateThread: (input: {
    object_ids: string[]
    title: string
    priority: MarkupThreadPriority
    message: string
  }) => Promise<boolean>
  onReplyThread: (threadId: string, text: string) => Promise<boolean>
  onSetThreadStatus: (threadId: string, action: 'resolve' | 'reopen') => Promise<boolean>
  onSetThreadPriority: (threadId: string, priority: MarkupThreadPriority) => Promise<boolean>
  onDeleteThread: (thread: MarkupThread) => Promise<boolean>
  onToggleThreadVisibility: (thread: MarkupThread) => void
  onViewObject?: (objectId: string) => void
  onAddComment: (text: string, priority: PartCommentPriority) => Promise<boolean>
  onReplyComment: (commentId: string, text: string) => Promise<boolean>
  onSetCommentStatus: (commentId: string, status: 'open' | 'resolved') => Promise<boolean>
  onSetCommentPriority: (commentId: string, priority: PartCommentPriority) => Promise<boolean>
  onDeleteComment: (comment: PartCommentRow) => Promise<boolean>
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

function statusBadge(status: 'open' | 'resolved') {
  return (
    <span className={`badge ${status === 'open' ? 'text-bg-warning' : 'text-bg-success'}`}>
      {status}
    </span>
  )
}

function kindChip(kind: 'thread' | 'comment') {
  return (
    <span className="badge text-bg-light border pd-markup-kind" title={kind === 'thread' ? 'Drawing markup review' : 'General comment'}>
      <i className={`pi ${kind === 'thread' ? 'pi-pencil' : 'pi-comment'}`} aria-hidden="true" />
    </span>
  )
}

function prioritySelect({
  value,
  allowNone,
  disabled,
  onChange,
  label,
}: {
  value: string
  allowNone: boolean
  disabled: boolean
  onChange: (next: string) => void
  label: string
}) {
  const cls =
    value === 'high' ? 'pd-markup-priority-select--high' : value === 'normal' ? 'pd-markup-priority-select--normal' : value === 'low' ? 'pd-markup-priority-select--low' : ''
  return (
    <select
      className={`form-select form-select-sm pd-markup-priority-select ${cls}`}
      value={value}
      disabled={disabled}
      onChange={(e) => onChange(e.target.value)}
      aria-label={label}
      title={label}
    >
      {allowNone ? <option value="">no importance</option> : null}
      <option value="low">low</option>
      <option value="normal">normal</option>
      <option value="high">high</option>
    </select>
  )
}

function textIncludes(needle: string, ...values: (string | null | undefined)[]): boolean {
  return values.some((value) => String(value || '').toLowerCase().includes(needle))
}

function threadMatchesFilter(thread: MarkupThread, needle: string): boolean {
  if (!needle) return true
  if (
    textIncludes(
      needle,
      thread.title,
      thread.status,
      thread.priority,
      thread.created_by,
      thread.created_by_display,
      thread.created_at_display,
      thread.created_at,
    )
  ) {
    return true
  }
  return (thread.messages || []).some((msg) =>
    textIncludes(needle, msg.text, msg.author, msg.author_display, msg.ts_display, msg.ts),
  )
}

function commentMatchesFilter(comment: PartCommentRow, needle: string): boolean {
  if (!needle) return true
  if (
    textIncludes(
      needle,
      comment.text,
      comment.status || 'open',
      comment.priority,
      comment.author,
      comment.author_display,
      comment.ts_display,
      comment.ts,
    )
  ) {
    return true
  }
  return (comment.replies || []).some((reply) =>
    textIncludes(needle, reply.text, reply.author, reply.author_display, reply.ts_display, reply.ts),
  )
}

export default function MarkupThreadsPanel({
  partNumber,
  revision,
  threads,
  comments,
  canEditThreads,
  canComment,
  selectedObjectIds,
  busy,
  commentsBusy,
  loading,
  error,
  commentsError,
  filterText,
  textMatches,
  promptObjectIds,
  hiddenObjectIds,
  onPromptDismiss,
  onCreateThread,
  onReplyThread,
  onSetThreadStatus,
  onSetThreadPriority,
  onDeleteThread,
  onToggleThreadVisibility,
  onViewObject,
  onAddComment,
  onReplyComment,
  onSetCommentStatus,
  onSetCommentPriority,
  onDeleteComment,
}: Props) {
  const [filter, setFilter] = useState<StatusFilter>('open')
  const [creating, setCreating] = useState(false)
  const [title, setTitle] = useState('')
  const [priority, setPriority] = useState<MarkupThreadPriority>('normal')
  const [commentPriority, setCommentPriority] = useState<PartCommentPriority>('')
  const [message, setMessage] = useState('')
  const [replyDrafts, setReplyDrafts] = useState<Record<string, string>>({})

  const anyBusy = busy || !!commentsBusy
  const prompted = !!(promptObjectIds && promptObjectIds.length)
  const linkIds = prompted ? promptObjectIds! : selectedObjectIds
  // Selected/just-drawn markup objects turn the composer into a review-thread
  // form; with nothing selected it posts a general comment.
  const threadMode = canEditThreads && linkIds.length > 0

  // A freshly drawn markup opens the review form automatically.
  useEffect(() => {
    if (prompted) setCreating(true)
  }, [prompted, promptObjectIds])

  const needle = String(filterText || '').trim().toLowerCase()
  const hiddenIds = useMemo(() => new Set(hiddenObjectIds || []), [hiddenObjectIds])

  const items = useMemo<ReviewListItem[]>(() => {
    const rows: ReviewListItem[] = [
      ...threads.map((thread) => ({ kind: 'thread' as const, ts: thread.created_at || '', thread })),
      ...comments.map((comment) => ({ kind: 'comment' as const, ts: comment.ts || '', comment })),
    ]
    rows.sort((a, b) => String(a.ts).localeCompare(String(b.ts)))
    return rows
  }, [threads, comments])

  const openCount = useMemo(
    () =>
      threads.filter((t) => t.status === 'open').length +
      comments.filter((c) => (c.status || 'open') === 'open').length,
    [threads, comments],
  )

  const visible = useMemo(() => {
    return items.filter((item) => {
      const status = item.kind === 'thread' ? item.thread.status : item.comment.status || 'open'
      if (!needle && filter !== 'all' && status !== filter) return false
      if (needle) {
        return item.kind === 'thread'
          ? threadMatchesFilter(item.thread, needle)
          : commentMatchesFilter(item.comment, needle)
      }
      return true
    })
  }, [items, filter, needle])

  function closeForm() {
    setCreating(false)
    setTitle('')
    setPriority('normal')
    setCommentPriority('')
    setMessage('')
    onPromptDismiss?.()
  }

  async function submitComposer() {
    const text = message.trim()
    if (!text) return
    let ok = false
    if (threadMode) {
      if (!title.trim() || !linkIds.length) return
      ok = await onCreateThread({ object_ids: linkIds, title: title.trim(), priority, message: text })
    } else {
      ok = await onAddComment(text, commentPriority)
    }
    if (ok) closeForm()
  }

  async function submitReply(item: ReviewListItem) {
    const key = item.kind === 'thread' ? item.thread.id : item.comment.id || ''
    const text = (replyDrafts[key] || '').trim()
    if (!key || !text) return
    const ok = item.kind === 'thread' ? await onReplyThread(key, text) : await onReplyComment(key, text)
    if (ok) setReplyDrafts((prev) => ({ ...prev, [key]: '' }))
  }

  const composerReady = threadMode ? !!title.trim() && !!message.trim() : !!message.trim()

  function renderMessage(msg: { id: string; author?: string; author_display?: string; author_profile?: MarkupIdentityProfile | null; ts?: string | null; ts_display?: string | null; ts_local?: string | null; text: string }) {
    return (
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
    )
  }

  function renderReplyBox(item: ReviewListItem, canAct: boolean) {
    if (!canAct) return null
    const key = item.kind === 'thread' ? item.thread.id : item.comment.id || ''
    if (!key) return null
    const label = item.kind === 'thread' ? `Reply to review ${key}` : `Reply to comment ${key}`
    return (
      <div className="input-group input-group-sm mt-2">
        <MentionTextarea
          partNumber={partNumber}
          revision={revision}
          className="form-control form-control-sm"
          rows={1}
          placeholder="Reply..."
          value={replyDrafts[key] || ''}
          onChange={(value) => setReplyDrafts((prev) => ({ ...prev, [key]: value }))}
          onKeyDown={(e) => {
            if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && (replyDrafts[key] || '').trim() && !anyBusy) {
              e.preventDefault()
              submitReply(item)
            }
          }}
          ariaLabel={label}
        />
        <button
          type="button"
          className="btn btn-outline-primary"
          disabled={anyBusy || !(replyDrafts[key] || '').trim()}
          onClick={() => submitReply(item)}
        >
          Reply
        </button>
      </div>
    )
  }

  function renderThreadItem(thread: MarkupThread) {
    const threadHidden = !!thread.object_ids.length && thread.object_ids.every((id) => hiddenIds.has(id))
    return (
      <div key={`thread-${thread.id}`} className={`pd-markup-thread border rounded p-2 ${thread.status === 'resolved' ? 'pd-markup-thread--resolved' : ''}`}>
        <div className="pd-markup-thread-head">
          <div className="pd-markup-thread-title">
            {kindChip('thread')}
            {canEditThreads
              ? prioritySelect({
                  value: thread.priority,
                  allowNone: false,
                  disabled: anyBusy,
                  onChange: (next) => {
                    if (next === 'low' || next === 'normal' || next === 'high') onSetThreadPriority(thread.id, next)
                  },
                  label: 'Review importance',
                })
              : <span className={`badge ${thread.priority === 'high' ? 'text-bg-danger' : thread.priority === 'low' ? 'text-bg-secondary' : 'text-bg-info'} pd-markup-priority`}>{thread.priority}</span>}
            {statusBadge(thread.status)}
            <span className="fw-semibold">{thread.title || thread.messages[0]?.text?.slice(0, 60) || 'Review thread'}</span>
          </div>
          <div className="pd-markup-thread-actions">
            {thread.linked ? (
              <button
                type="button"
                className={`btn btn-sm ${threadHidden ? 'btn-outline-primary' : 'btn-outline-secondary'}`}
                title={threadHidden ? 'Show and focus this markup' : 'Hide this markup from the drawing'}
                aria-pressed={!threadHidden}
                onClick={() => onToggleThreadVisibility(thread)}
              >
                <i className={`pi ${threadHidden ? 'pi-eye' : 'pi-eye-slash'} me-1`} aria-hidden="true" />
                {threadHidden ? 'View' : 'Hide'}
              </button>
            ) : (
              <span className="badge text-bg-light border" title="The linked markup object was removed">
                Markup no longer present
              </span>
            )}
            {canEditThreads ? (
              <>
                {thread.status === 'open' ? (
                  <button type="button" className="btn btn-sm btn-outline-success" disabled={anyBusy} onClick={() => onSetThreadStatus(thread.id, 'resolve')}>
                    Resolve
                  </button>
                ) : (
                  <button type="button" className="btn btn-sm btn-outline-warning" disabled={anyBusy} onClick={() => onSetThreadStatus(thread.id, 'reopen')}>
                    Reopen
                  </button>
                )}
                <button
                  type="button"
                  className="btn btn-sm btn-outline-danger"
                  title="Delete this review thread (markup objects stay on the drawing)"
                  aria-label="Delete review thread"
                  disabled={anyBusy}
                  onClick={() => onDeleteThread(thread)}
                >
                  <i className="pi pi-trash" aria-hidden="true" />
                </button>
              </>
            ) : null}
          </div>
        </div>

        <div className="pd-markup-messages">{thread.messages.map((msg) => renderMessage(msg))}</div>

        {thread.status === 'resolved' && thread.resolved_at_display ? (
          <div className="text-muted small mt-1">
            Resolved by {thread.resolved_by || 'unknown'} - {thread.resolved_at_display}
          </div>
        ) : null}

        {renderReplyBox({ kind: 'thread', ts: thread.created_at || '', thread }, canEditThreads)}
      </div>
    )
  }

  function renderCommentItem(comment: PartCommentRow) {
    const status = comment.status || 'open'
    const hasId = !!comment.id
    return (
      <div key={`comment-${comment.id || comment.ts}`} className={`pd-markup-thread border rounded p-2 ${status === 'resolved' ? 'pd-markup-thread--resolved' : ''}`}>
        <div className="pd-markup-thread-head">
          <div className="pd-markup-thread-title">
            {kindChip('comment')}
            {canComment && hasId
              ? prioritySelect({
                  value: comment.priority || '',
                  allowNone: true,
                  disabled: anyBusy,
                  onChange: (next) => onSetCommentPriority(comment.id!, next as PartCommentPriority),
                  label: 'Comment importance',
                })
              : comment.priority
              ? <span className={`badge ${comment.priority === 'high' ? 'text-bg-danger' : comment.priority === 'low' ? 'text-bg-secondary' : 'text-bg-info'} pd-markup-priority`}>{comment.priority}</span>
              : null}
            {statusBadge(status)}
          </div>
          <div className="pd-markup-thread-actions">
            {canComment && hasId ? (
              <>
                {status === 'open' ? (
                  <button type="button" className="btn btn-sm btn-outline-success" disabled={anyBusy} onClick={() => onSetCommentStatus(comment.id!, 'resolved')}>
                    Resolve
                  </button>
                ) : (
                  <button type="button" className="btn btn-sm btn-outline-warning" disabled={anyBusy} onClick={() => onSetCommentStatus(comment.id!, 'open')}>
                    Reopen
                  </button>
                )}
              </>
            ) : null}
            {canComment ? (
              <button
                type="button"
                className="btn btn-sm btn-outline-danger"
                title="Erase this comment"
                aria-label="Erase comment"
                disabled={anyBusy}
                onClick={() => onDeleteComment(comment)}
              >
                <i className="pi pi-trash" aria-hidden="true" />
              </button>
            ) : null}
          </div>
        </div>

        <div className="pd-markup-messages">
          {renderMessage({
            id: comment.id || comment.ts || 'comment',
            author: comment.author,
            author_display: comment.author_display,
            author_profile: comment.author_profile,
            ts: comment.ts,
            ts_display: comment.ts_display,
            ts_local: comment.ts_local,
            text: comment.text,
          })}
          {(comment.replies || []).map((reply) => renderMessage(reply))}
        </div>

        {renderReplyBox({ kind: 'comment', ts: comment.ts || '', comment }, canComment && hasId)}
      </div>
    )
  }

  return (
    <div className="pd-markup-panel pd-card">
      <div className="pd-markup-panel-head">
        <h6 className="mb-0 d-flex align-items-center gap-2">
          Comments & reviews
          <span className="badge rounded-pill text-bg-secondary">{items.length}</span>
          {openCount > 0 ? <span className="badge rounded-pill text-bg-warning">{openCount} open</span> : null}
        </h6>
        <div className="btn-group btn-group-sm" role="group" aria-label="Filter by status">
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

      {canComment || canEditThreads ? (
        <div className="pd-markup-newthread">
          {!creating ? (
            <>
              <button
                type="button"
                className="btn btn-sm btn-outline-primary"
                disabled={anyBusy || (!canComment && !threadMode)}
                onClick={() => setCreating(true)}
              >
                <i className="pi pi-comments me-1" aria-hidden="true" />
                {threadMode
                  ? `Add review comment (${linkIds.length} object${linkIds.length > 1 ? 's' : ''})`
                  : 'Add comment'}
              </button>
              {canEditThreads && !threadMode ? (
                <div className="text-muted small mt-1">
                  Select markup objects on the drawing to attach the comment as a markup review.
                </div>
              ) : null}
            </>
          ) : (
            <div className="pd-markup-newthread-form border rounded p-2">
              <div className="small fw-semibold mb-1">
                {threadMode
                  ? `${prompted ? 'Describe the new markup' : 'New markup review'} (${linkIds.length} linked object${linkIds.length > 1 ? 's' : ''})`
                  : 'New comment'}
              </div>
              {threadMode ? (
                <>
                  <input
                    type="text"
                    className="form-control form-control-sm mb-1"
                    placeholder="Review title"
                    maxLength={200}
                    value={title}
                    onChange={(e) => setTitle(e.target.value)}
                    aria-label="Review title"
                  />
                  <select
                    className="form-select form-select-sm mb-1"
                    value={priority}
                    onChange={(e) => setPriority(e.target.value as MarkupThreadPriority)}
                    aria-label="Review priority"
                  >
                    <option value="low">Low priority</option>
                    <option value="normal">Normal priority</option>
                    <option value="high">High priority</option>
                  </select>
                </>
              ) : (
                <select
                  className="form-select form-select-sm mb-1"
                  value={commentPriority}
                  onChange={(e) => setCommentPriority(e.target.value as PartCommentPriority)}
                  aria-label="Comment importance"
                >
                  <option value="">No importance</option>
                  <option value="low">Low importance</option>
                  <option value="normal">Normal importance</option>
                  <option value="high">High importance</option>
                </select>
              )}
              <MentionTextarea
                partNumber={partNumber}
                revision={revision}
                className="form-control form-control-sm mb-1"
                rows={3}
                placeholder={threadMode ? 'Describe the issue or request...' : 'Add a comment...'}
                autoFocus={prompted}
                value={message}
                onChange={setMessage}
                onKeyDown={(e) => {
                  if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && composerReady && !anyBusy) {
                    e.preventDefault()
                    submitComposer()
                  }
                }}
                ariaLabel={threadMode ? 'Initial review message' : 'Comment text'}
              />
              <div className="d-flex gap-2">
                <button type="button" className="btn btn-sm btn-primary" disabled={anyBusy || !composerReady} onClick={submitComposer}>
                  {anyBusy ? 'Saving...' : threadMode ? 'Create review' : 'Post comment'}
                </button>
                <button type="button" className="btn btn-sm btn-outline-secondary" disabled={anyBusy} onClick={closeForm}>
                  {prompted ? 'Skip' : 'Cancel'}
                </button>
              </div>
              {threadMode && prompted ? (
                <div className="text-muted small mt-1">Saving the review also saves the markup layer.</div>
              ) : null}
            </div>
          )}
        </div>
      ) : null}

      {error ? <div className="alert alert-danger py-1 px-2 small my-2">{error}</div> : null}
      {commentsError ? <div className="alert alert-danger py-1 px-2 small my-2">{commentsError}</div> : null}

      {needle && textMatches && textMatches.length ? (
        <div className="pd-markup-textmatches">
          <div className="small fw-semibold">Markup text matches ({textMatches.length})</div>
          {textMatches.map((match) => (
            <div key={match.id} className="pd-markup-textmatch small">
              <span className="pd-markup-textmatch-text" title={match.text}>
                <i className="pi pi-language me-1" aria-hidden="true" />
                {match.text.length > 60 ? `${match.text.slice(0, 60)}…` : match.text}
              </span>
              {onViewObject ? (
                <button type="button" className="btn btn-sm btn-outline-secondary" onClick={() => onViewObject(match.id)}>
                  <i className="pi pi-eye" aria-hidden="true" />
                </button>
              ) : null}
            </div>
          ))}
        </div>
      ) : null}

      <div className="pd-markup-threadlist">
        {loading ? (
          <div className="text-muted small">Loading comments & reviews...</div>
        ) : visible.length === 0 ? (
          <div className="text-muted small pd-markup-empty">
            {items.length === 0
              ? 'No comments or reviews yet. Post a comment, or draw a markup on the drawing to start a review.'
              : needle
              ? 'Nothing matches the search.'
              : `No ${filter} items.`}
          </div>
        ) : (
          visible.map((item) => (item.kind === 'thread' ? renderThreadItem(item.thread) : renderCommentItem(item.comment)))
        )}
      </div>
    </div>
  )
}
