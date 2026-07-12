import { useRef, useState, type KeyboardEvent } from 'react'

type MentionUser = {
  id: string
  email: string
  profile?: { label?: string; initials?: string; avatar_color?: string }
}

type Props = {
  value: string
  onChange: (value: string) => void
  rows?: number
  className?: string
  placeholder?: string
  disabled?: boolean
  autoFocus?: boolean
  maxLength?: number
  ariaLabel?: string
  partNumber: string
  revision?: string
  onKeyDown?: (event: KeyboardEvent<HTMLTextAreaElement>) => void
}

const EMOJIS = ['👍', '✅', '👀', '⚠️', '🚨', '🔧', '📐', '💡', '🎉', '🙂']

export default function MentionTextarea({
  value,
  onChange,
  rows = 2,
  className = 'form-control',
  placeholder,
  disabled,
  autoFocus,
  maxLength,
  ariaLabel,
  partNumber,
  revision,
  onKeyDown,
}: Props) {
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)
  const searchTimerRef = useRef<number | null>(null)
  const requestRef = useRef(0)
  const mentionRangeRef = useRef<{ start: number; end: number } | null>(null)
  const [suggestions, setSuggestions] = useState<MentionUser[]>([])
  const [activeSuggestion, setActiveSuggestion] = useState(0)
  const [emojiOpen, setEmojiOpen] = useState(false)

  function closeSuggestions() {
    mentionRangeRef.current = null
    setSuggestions([])
    setActiveSuggestion(0)
  }

  function findMention(nextValue: string, caret: number) {
    const before = nextValue.slice(0, caret)
    const match = before.match(/(?:^|\s)@([^\s@]*)$/)
    if (!match) return null
    const query = match[1] || ''
    return { query, start: caret - query.length - 1, end: caret }
  }

  function loadSuggestions(nextValue: string, caret: number) {
    if (searchTimerRef.current) window.clearTimeout(searchTimerRef.current)
    const mention = findMention(nextValue, caret)
    if (!mention) {
      closeSuggestions()
      return
    }
    mentionRangeRef.current = { start: mention.start, end: mention.end }
    const requestId = ++requestRef.current
    searchTimerRef.current = window.setTimeout(async () => {
      try {
        const params = new URLSearchParams({ q: mention.query, pn: partNumber, rev: revision || '' })
        const response = await fetch(`/api/users/mentionable?${params.toString()}`)
        const data = await response.json().catch(() => null)
        if (requestId !== requestRef.current || !response.ok) return
        setSuggestions(Array.isArray(data?.users) ? data.users : [])
        setActiveSuggestion(0)
      } catch {
        if (requestId === requestRef.current) closeSuggestions()
      }
    }, 140)
  }

  function replaceSelection(text: string, range?: { start: number; end: number } | null) {
    const textarea = textareaRef.current
    const start = range?.start ?? textarea?.selectionStart ?? value.length
    const end = range?.end ?? textarea?.selectionEnd ?? start
    const next = `${value.slice(0, start)}${text}${value.slice(end)}`
    onChange(next)
    const caret = start + text.length
    window.requestAnimationFrame(() => {
      textareaRef.current?.focus()
      textareaRef.current?.setSelectionRange(caret, caret)
    })
  }

  function chooseMention(user: MentionUser) {
    replaceSelection(`@${user.email} `, mentionRangeRef.current)
    closeSuggestions()
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (suggestions.length) {
      if (event.key === 'ArrowDown' || event.key === 'ArrowUp') {
        event.preventDefault()
        const step = event.key === 'ArrowDown' ? 1 : -1
        setActiveSuggestion((current) => (current + step + suggestions.length) % suggestions.length)
        return
      }
      if (event.key === 'Enter' || event.key === 'Tab') {
        event.preventDefault()
        const selected = suggestions[activeSuggestion]
        if (selected) chooseMention(selected)
        return
      }
      if (event.key === 'Escape') {
        event.preventDefault()
        closeSuggestions()
        return
      }
    }
    onKeyDown?.(event)
  }

  return (
    <div className="tm-mention-composer">
      <textarea
        ref={textareaRef}
        className={className}
        rows={rows}
        value={value}
        placeholder={placeholder}
        disabled={disabled}
        autoFocus={autoFocus}
        maxLength={maxLength}
        aria-label={ariaLabel}
        onChange={(event) => {
          const next = event.target.value
          onChange(next)
          loadSuggestions(next, event.target.selectionStart ?? next.length)
        }}
        onClick={(event) => loadSuggestions(value, event.currentTarget.selectionStart ?? value.length)}
        onKeyDown={handleKeyDown}
        onBlur={() => window.setTimeout(closeSuggestions, 120)}
      />

      {suggestions.length ? (
        <div className="tm-mention-menu" role="listbox" aria-label="Mention a user">
          {suggestions.map((user, index) => (
            <button
              key={user.id}
              type="button"
              className={`tm-mention-option${index === activeSuggestion ? ' active' : ''}`}
              role="option"
              aria-selected={index === activeSuggestion}
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => chooseMention(user)}
            >
              <span className="tm-mention-avatar" style={{ background: user.profile?.avatar_color || '#1d4ed8' }} aria-hidden="true">
                {user.profile?.initials || user.email.slice(0, 2).toUpperCase()}
              </span>
              <span><strong>{user.profile?.label || user.email}</strong><small>{user.email}</small></span>
            </button>
          ))}
        </div>
      ) : null}

      <div className="tm-composer-tools">
        <button
          type="button"
          className="btn btn-sm btn-link"
          title="Add emoji"
          aria-label="Add emoji"
          aria-expanded={emojiOpen}
          onClick={() => setEmojiOpen((open) => !open)}
        >
          <span aria-hidden="true">🙂</span>
        </button>
        <span className="tm-mention-hint">Use @ to mention</span>
      </div>
      {emojiOpen ? (
        <div className="tm-emoji-menu" aria-label="Choose an emoji">
          {EMOJIS.map((emoji) => (
            <button
              key={emoji}
              type="button"
              onMouseDown={(event) => event.preventDefault()}
              onClick={() => {
                replaceSelection(emoji)
                setEmojiOpen(false)
              }}
            >
              {emoji}
            </button>
          ))}
        </div>
      ) : null}
    </div>
  )
}
