import { useSyncExternalStore } from 'react'
import { getSession, subscribe } from '../../api/auth'

export function useSession() {
  return useSyncExternalStore(subscribe, getSession, getSession)
}
