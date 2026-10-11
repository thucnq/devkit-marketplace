import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { api } from '../../api/client'

// Replace these hand-written types with `npm run gen:api` output (src/api/schema.d.ts) in real features.
export type Note = {
  id: string
  title: string
  content?: string
  ownerId: string
  createdAt: string
  updatedAt: string
  version: number
}
export type Page<T> = { items: T[]; page: number; size: number; total: number }

export function useNotes(page = 0) {
  return useQuery({
    queryKey: ['notes', page],
    queryFn: () => api<Page<Note>>(`/api/notes?page=${page}&size=20`),
  })
}

export function useCreateNote() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: (body: { title: string; content?: string }) =>
      api<Note>('/api/notes', { method: 'POST', body: JSON.stringify(body) }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ['notes'] }),
  })
}
