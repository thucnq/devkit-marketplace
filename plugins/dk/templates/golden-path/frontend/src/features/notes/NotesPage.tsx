import { useState, type FormEvent } from 'react'
import { ApiError } from '../../api/errors'
import { vi } from '../../i18n/vi'
import { useCreateNote, useNotes } from './api'

export function NotesPage() {
  const notes = useNotes()
  const create = useCreateNote()
  const [title, setTitle] = useState('')

  function onSubmit(e: FormEvent) {
    e.preventDefault()
    create.mutate({ title }, { onSuccess: () => setTitle('') })
  }

  return (
    <main>
      <h1>{vi.notes.title}</h1>
      <form onSubmit={onSubmit} className="row">
        <label>
          {vi.notes.newTitle}
          <input
            required
            maxLength={200}
            value={title}
            onChange={(e) => setTitle(e.target.value)}
          />
        </label>
        <button type="submit" disabled={create.isPending}>
          {vi.notes.create}
        </button>
      </form>
      {create.error instanceof ApiError && <p role="alert">{create.error.detail}</p>}

      {notes.isPending && <p role="status">{vi.common.loading}</p>}
      {notes.isError && (
        <p role="alert">
          {notes.error instanceof ApiError ? notes.error.detail : String(notes.error)}{' '}
          <button onClick={() => void notes.refetch()}>{vi.common.retry}</button>
        </p>
      )}
      {notes.data && notes.data.items.length === 0 && <p>{vi.notes.empty}</p>}
      {notes.data && notes.data.items.length > 0 && (
        <ul>
          {notes.data.items.map((n) => (
            <li key={n.id}>{n.title}</li>
          ))}
        </ul>
      )}
    </main>
  )
}
