import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { createMemoryRouter, RouterProvider } from 'react-router'
import { describe, expect, it } from 'vitest'
import { getSession } from '../../api/auth'
import { mockApi } from '../../test/server'
import { LoginPage } from './LoginPage'

function renderAt(path = '/login') {
  const router = createMemoryRouter(
    [
      { path: '/login', element: <LoginPage /> },
      { path: '/notes', element: <p>notes page</p> },
    ],
    { initialEntries: [path] },
  )
  render(<RouterProvider router={router} />)
}

describe('LoginPage', () => {
  it('AC-AUTH-01 (UI): logs in and goes to notes', async () => {
    mockApi([
      {
        method: 'POST',
        path: '/api/auth/login',
        body: {
          accessToken: 't',
          expiresIn: 900,
          user: { id: '1', tenantId: '2', email: 'a@b.vn', fullName: 'A', roles: ['USER'] },
        },
      },
    ])
    renderAt()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.vn')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'secret')
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByText('notes page')).toBeInTheDocument()
    expect(getSession()?.accessToken).toBe('t')
  })

  it('AC-AUTH-02 (UI): shows the server message on wrong password', async () => {
    mockApi([
      {
        method: 'POST',
        path: '/api/auth/login',
        status: 401,
        body: { detail: 'Email hoặc mật khẩu không đúng.' },
      },
    ])
    renderAt()
    await userEvent.type(screen.getByLabelText('Email'), 'a@b.vn')
    await userEvent.type(screen.getByLabelText('Mật khẩu'), 'wrong')
    await userEvent.click(screen.getByRole('button', { name: 'Đăng nhập' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Email hoặc mật khẩu không đúng.')
  })

  it('shows SSO error from the redirect', () => {
    mockApi([])
    renderAt('/login?error=sso_not_invited')
    expect(screen.getByRole('alert')).toHaveTextContent('chưa được mời')
  })
})
