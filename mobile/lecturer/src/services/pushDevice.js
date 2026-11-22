// The phone side of push (S19): what pushRegistration.js needs, from Expo. expo-notifications is
// loaded only where push can work (a development or store build on a phone), so Expo Go on
// Android and the browser never load it. The same file is in the student app.
import { Platform } from 'react-native'
import Constants from 'expo-constants'
import AsyncStorage from '@react-native-async-storage/async-storage'

const KEY = 'push_token'

const platform = Platform.OS
const isExpoGo = Constants.executionEnvironment === 'storeClient'
const projectId = Constants.expoConfig?.extra?.eas?.projectId ?? Constants.easConfig?.projectId ?? null
const pushPossible = (platform === 'android' || platform === 'ios') && !(isExpoGo && platform === 'android') && !!projectId

let _N = null
function notificationsModule() {
  if (!_N) {
    _N = require('expo-notifications')
    // A push that arrives while the app is open still shows as a banner; the feed updates live too
    _N.setNotificationHandler({
      handleNotification: async () => ({
        shouldShowBanner: true, shouldShowList: true, shouldPlaySound: false, shouldSetBadge: false,
      }),
    })
  }
  return _N
}

export const pushEnv = {
  platform,
  isExpoGo,
  projectId,
  getNotifications: notificationsModule,
  store: {
    get: () => AsyncStorage.getItem(KEY),
    set: (t) => AsyncStorage.setItem(KEY, t),
    clear: () => AsyncStorage.removeItem(KEY),
  },
  log: (msg) => console.log(msg),
}

// Tapping a push opens its link (data.link from the server). Returns an unsubscribe function.
export function onPushTapped(openLink) {
  if (!pushPossible) return () => {}
  try {
    const sub = notificationsModule().addNotificationResponseReceivedListener((response) => {
      const link = response?.notification?.request?.content?.data?.link
      if (link) openLink(link)
    })
    return () => sub?.remove?.()
  } catch {
    return () => {}
  }
}
