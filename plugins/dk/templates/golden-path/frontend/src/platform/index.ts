import { Capacitor } from '@capacitor/core'

/** Thin adapter so features never call browser-only or native-only APIs directly. */
export const platform = {
  isNative: () => Capacitor.isNativePlatform(),
}
