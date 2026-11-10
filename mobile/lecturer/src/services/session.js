// Restoring the signed-in session when the app starts (web reload or phone restart).
// Pure: the caller passes in whether a token is stored and how to load /auth/me, so this
// runs under `node --test`. /auth/me already refreshes an expired access token (client.js).

export const APP_ROLES = ['lecturer', 'admin']

// -> { user } to sign straight in, or { user: null, signOut } where signOut says the stored
// tokens are no good (rejected, deactivated, or a student's) and should be cleared.
// A network failure keeps them, so the next start can try again.
export async function restoreSession({ hasStoredSession, fetchMe }) {
  if (!hasStoredSession) return { user: null, signOut: false }
  try {
    const user = await fetchMe()
    if (!APP_ROLES.includes(user.roleKey)) return { user: null, signOut: true }
    return { user, signOut: false }
  } catch (e) {
    return { user: null, signOut: e.status === 401 || e.status === 403 }
  }
}
