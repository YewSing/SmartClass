// Open a source cited in a lecturer's "ask my materials" answer (FR-815). The lecturer file
// endpoint needs the Bearer token, so on web the file is fetched and opened in a new tab, and on
// a phone it is downloaded and handed to a viewer app (Android) or the share sheet (iOS).
import { Platform } from 'react-native'
import * as FileSystem from 'expo-file-system/legacy'
import * as Sharing from 'expo-sharing'
import { apiCallRaw, BASE, getToken } from './client'

const EXT = {
  'application/pdf': '.pdf',
  'application/vnd.openxmlformats-officedocument.presentationml.presentation': '.pptx',
  'application/vnd.openxmlformats-officedocument.wordprocessingml.document': '.docx',
  'text/plain': '.txt',
}

function header(headers, name) {
  const key = Object.keys(headers ?? {}).find(k => k.toLowerCase() === name)
  return key ? headers[key] : ''
}

export function lecturerFileUrl(materialId) {
  return `/lecturer/assistant/materials/${materialId}/file`
}

export async function openLecturerSource(citation) {
  if (Platform.OS === 'web') {
    // Open the tab now, while the click still counts as the user's: a tab opened after the
    // download finishes is blocked as a pop-up by most browsers.
    const tab = window.open('', '_blank')
    try {
      const res = await apiCallRaw('GET', lecturerFileUrl(citation.material_id))
      const url = URL.createObjectURL(await res.blob())
      const target = `${url}#page=${citation.open_page}`
      if (tab) tab.location.href = target
      else window.open(target, '_blank')
    } catch (e) {
      tab?.close()
      throw e
    }
    return
  }

  const tmp = `${FileSystem.cacheDirectory}material-${citation.material_id}`
  const res = await FileSystem.downloadAsync(`${BASE}${lecturerFileUrl(citation.material_id)}`, tmp, {
    headers: { Authorization: `Bearer ${getToken()}` },
  })
  if (res.status !== 200) {
    await FileSystem.deleteAsync(res.uri, { idempotent: true })
    throw new Error(`Couldn't open the file (HTTP ${res.status}).`)
  }
  const mime = header(res.headers, 'content-type').split(';')[0].trim() || 'application/octet-stream'
  const uri = `${tmp}${EXT[mime] ?? ''}`
  if (uri !== tmp) {
    await FileSystem.deleteAsync(uri, { idempotent: true })
    await FileSystem.moveAsync({ from: tmp, to: uri })
  }

  if (!(await Sharing.isAvailableAsync())) throw new Error('No app on this phone can open this file.')
  await Sharing.shareAsync(uri, { mimeType: mime, dialogTitle: citation.title })
}

// "slide 4" / "page 12" — where to look once the file is open
export function openAtLabel(citation) {
  const kind = citation.location_type === 'slide' ? 'slide' : citation.location_type === 'page' ? 'page' : 'section'
  return `${kind} ${citation.open_page}`
}
