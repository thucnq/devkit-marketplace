import type { CapacitorConfig } from '@capacitor/cli'

// Mobile app = the same web build wrapped by Capacitor (npm run cap:add:android, then cap:sync).
const config: CapacitorConfig = {
  appId: 'vn.goldenpath.app',
  appName: 'goldenpath',
  webDir: 'dist',
}

export default config
