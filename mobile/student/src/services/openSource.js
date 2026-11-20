// Open a cited course file (FR-809). The file endpoint needs the Bearer token, so the app
// downloads it into the cache and hands it to a viewer app (Android) or the share sheet (iOS).
import { Platform } from 'react-native'
import * as FileSystem from 'expo-file-system/legacy'
import * as IntentLauncher from 'expo-intent-launcher'
import * as Sharing from 'expo-sharing'
import { BASE, getToken, refreshAccessToken } from './client'

const EXT = {
  'application/pdf': '.pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
  'application/vnd.ms-powerpoint': '.ppt',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
  'application/msword': '.doc',
  'text/plain': '.txt',
}

const STATUS_MESSAGE = {
  403: 'You are not enrolled in this course.',
  404: 'This material has no file to open.',
  502: "Couldn't get the file from SPeCTRUM. Try again later.",
}

function header(headers, name) {
  const key = Object.keys(headers ?? {}).find(k => k.toLowerCase() === name)
  return key ? headers[key] : ''
}

async function errorFor(status, readBody) {
  if (STATUS_MESSAGE[status]) return new Error(STATUS_MESSAGE[status])
  try {
    const body = JSON.parse(await readBody())
    if (body.detail) return new Error(body.detail)
  } catch { /* not JSON */ }
  return new Error(`Couldn't open the file (HTTP ${status}).`)
}

async function openOnWeb(citation) {
  // Open the tab now, while the tap still counts as the user's: a tab opened after the download
  // finishes is blocked as a pop-up by most browsers.
  const tab = window.open('', '_blank')
  try {
    const get = () => fetch(`${BASE}${citation.file_url}`, { headers: { Authorization: `Bearer ${getToken()}` } })
    let res = await get()
    if (res.status === 401 && await refreshAccessToken()) res = await get()
    if (!res.ok) throw await errorFor(res.status, () => res.text())
    const target = `${URL.createObjectURL(await res.blob())}#page=${citation.open_page}`
    if (tab) tab.location.href = target
    else window.open(target, '_blank')
  } catch (e) {
    tab?.close()
    throw e
  }
}

async function download(citation) {
  const tmp = `${FileSystem.cacheDirectory}material-${citation.material_id}`
  const get = () => FileSystem.downloadAsync(`${BASE}${citation.file_url}`, tmp, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  let res = await get()
  if (res.status === 401 && await refreshAccessToken()) res = await get()
  if (res.status !== 200) {
    const err = await errorFor(res.status, () => FileSystem.readAsStringAsync(res.uri))
    await FileSystem.deleteAsync(res.uri, { idempotent: true })
    throw err
  }
  const mime = header(res.headers, 'content-type').split(';')[0].trim() || 'application/octet-stream'
  // Viewers pick the file type from the extension
  const uri = `${tmp}${EXT[mime] ?? ''}`
  if (uri !== tmp) {
    await FileSystem.deleteAsync(uri, { idempotent: true })
    await FileSystem.moveAsync({ from: tmp, to: uri })
  }
  return { uri, mime }
}

export async function openCitedSource(citation) {
  if (Platform.OS === 'web') return openOnWeb(citation)

  const { uri, mime } = await download(citation)
  if (Platform.OS === 'android') {
    try {
      const contentUri = await FileSystem.getContentUriAsync(uri)
      await IntentLauncher.startActivityAsync('android.intent.action.VIEW', {
        data: contentUri,
        type: mime,
        flags: 1, // FLAG_GRANT_READ_URI_PERMISSION
      })
      return
    } catch {
      // No app for this file type: fall through to the share sheet
    }
  }
  if (!(await Sharing.isAvailableAsync())) throw new Error('No app on this phone can open this file.')
  await Sharing.shareAsync(uri, { mimeType: mime, dialogTitle: citation.title })
}

// Tapping a citation opens the file itself, with no passage screen in between (Yew Sing
// 2026-11-13): a PDF opens in the app at the cited page; slides and Word files open in another
// app (a new tab on web), and the chip already says which slide or section to go to.
export function openCitation(citation, navigation) {
  if (citation.location_type === 'page' && Platform.OS !== 'web') {
    navigation.navigate('AssistantPdf', { citation })
    return Promise.resolve()
  }
  return openCitedSource(citation)
}

// "slide 4" / "page 12" — where to look once the file is open
export function openAtLabel(citation) {
  const kind = citation.location_type === 'slide' ? 'slide' : citation.location_type === 'page' ? 'page' : 'section'
  return `${kind} ${citation.open_page}`
}
