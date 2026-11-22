// Expo push token registration (FR-210, FR-212; plan-shino.md S19). Every device call is passed in,
// so this runs under `npm test`; pushDevice.js supplies the real ones. The same file is in the
// lecturer app.
//
// After sign-in: ask for permission, get the Expo push token, POST /me/push-tokens and remember
// the token on the phone. On sign-out: DELETE /me/push-tokens/{token} (while still signed in) and
// forget it. Never throws: a phone without push still works in-app.

// Expo Go on Android has no remote push since SDK 53; a development build is needed for it.
export async function registerPush({ platform, isExpoGo, projectId, getNotifications, sendToken, store, log = () => {} }) {
  if (platform !== 'android' && platform !== 'ios') return { status: 'unsupported' }
  if (isExpoGo && platform === 'android') return { status: 'expo-go' }
  if (!projectId) return { status: 'no-project' }
  try {
    const N = getNotifications()
    let perm = await N.getPermissionsAsync()
    if (!perm?.granted) perm = await N.requestPermissionsAsync()
    if (!perm?.granted) return { status: 'denied' }
    if (platform === 'android') {
      await N.setNotificationChannelAsync('default', {
        name: 'SmartClass', importance: N.AndroidImportance?.HIGH ?? 4,
      })
    }
    const token = (await N.getExpoPushTokenAsync({ projectId }))?.data
    if (!token) return { status: 'error' }
    await sendToken(token, platform)
    await store.set(token)
    return { status: 'registered', token }
  } catch (e) {
    log(`push registration failed: ${e?.name ?? 'Error'}`)
    return { status: 'error' }
  }
}

// Call before the sign-in tokens are cleared: the DELETE needs them. The phone forgets the token only
// once the server has (or answers 404: already gone or moved to another account). After a failed
// DELETE it is kept, so the next sign-in on this phone registers it for whoever signs in instead.
export async function unregisterPush({ store, deleteToken }) {
  let token = null
  try { token = await store.get() } catch { return { status: 'none' } }
  if (!token) return { status: 'none' }
  try { await deleteToken(token) } catch (e) {
    if (e?.status !== 404) return { status: 'error' }
  }
  try { await store.clear() } catch { /* nothing more to do */ }
  return { status: 'removed' }
}
