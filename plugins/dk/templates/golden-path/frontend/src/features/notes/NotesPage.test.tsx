import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { mockApi } from '../../test/server'
import { NotesPage } from './NotesPage'

function renderPage() {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  render(
    <QueryClientProvider client={qc}>
      <NotesPage />
    </QueryClientProvider>,
  )
}

describe('NotesPage', () => {
  it('AC-NOTE-02 (UI): lists the notes returned by the API', async () => {
    mockApi([
      {
        path: '/api/notes',
        body: {
          items: [
            {
              id: '1',
              title: 'Họp khách hàng',
              ownerId: 'u',
              createdAt: '',
              updatedAt: '',
              version: 0,
            },
          ],
          page: 0,
          size: 20,
          total: 1,
        },
      },
    ])
    renderPage()
    expect(await screen.findByText('Họp khách hàng')).toBeInTheDocument()
  })

  it('shows the empty state', async () => {
    mockApi([{ path: '/api/notes', body: { items: [], page: 0, size: 20, total: 0 } }])
    renderPage()
    expect(await screen.findByText('Chưa có ghi chú nào.')).toBeInTheDocument()
  })

  it('shows the error state with retry', async () => {
    mockApi([{ path: '/api/notes', status: 500, body: { detail: 'Đã có lỗi xảy ra.' } }])
    renderPage()
    expect(await screen.findByRole('alert')).toHaveTextContent('Đã có lỗi xảy ra.')
  })
})
