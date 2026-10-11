import { createBrowserRouter, Navigate, RouterProvider } from 'react-router'
import { AuthCallback } from './features/auth/AuthCallback'
import { LoginPage } from './features/auth/LoginPage'
import { RequireAuth } from './features/auth/RequireAuth'
import { NotesPage } from './features/notes/NotesPage'

const router = createBrowserRouter([
  { path: '/', element: <Navigate to="/notes" replace /> },
  { path: '/login', element: <LoginPage /> },
  { path: '/auth/callback', element: <AuthCallback /> },
  {
    path: '/notes',
    element: (
      <RequireAuth>
        <NotesPage />
      </RequireAuth>
    ),
  },
])

export function App() {
  return <RouterProvider router={router} />
}
