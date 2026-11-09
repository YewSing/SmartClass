import { useMemo, useRef, useState } from 'react'
import { View, Text, TouchableOpacity, StyleSheet, ActivityIndicator } from 'react-native'
import { WebView } from 'react-native-webview'
import { Ionicons } from '@expo/vector-icons'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { BASE, getToken, refreshAccessToken } from '../services/client'
import { openCitedSource } from '../services/openSource'
import { buildPdfViewerHtml } from '../services/pdfViewerHtml'
import { C } from '../theme'

// In-app PDF viewer that opens at the cited page (FR-809)
export default function AssistantPdf({ route, navigation }) {
  const { citation } = route.params
  const { showToast } = useStudent()
  const [attempt, setAttempt] = useState(0)
  const [position, setPosition] = useState(null)
  const [error, setError] = useState(null)
  const [opening, setOpening] = useState(false)
  const refreshed = useRef(false)

  // eslint-disable-next-line react-hooks/exhaustive-deps -- rebuilt on purpose for each attempt, with the current token
  const html = useMemo(() => buildPdfViewerHtml({
    base: BASE, fileUrl: citation.file_url, token: getToken(), page: citation.open_page,
  }), [citation, attempt])

  const onMessage = async (event) => {
    const message = JSON.parse(event.nativeEvent.data)
    if (message.type === 'page') setPosition(message)
    else if (message.type === 'error') setError(message.message)
    else if (message.type === 'auth') {
      // The token expired: refresh once and load again
      if (!refreshed.current && await refreshAccessToken()) {
        refreshed.current = true
        setAttempt(n => n + 1)
      } else {
        setError('Your session has expired. Please sign in again.')
      }
    }
  }

  const retry = () => { setError(null); setPosition(null); setAttempt(n => n + 1) }

  const openElsewhere = async () => {
    setOpening(true)
    try {
      await openCitedSource(citation)
    } catch (e) {
      showToast(e.message, 'error')
    } finally {
      setOpening(false)
    }
  }

  return (
    <View style={styles.screen}>
      <Topbar
        title={citation.title}
        sub={position ? `Page ${position.page} of ${position.total}` : 'Opening PDF…'}
        onBack={() => navigation.goBack()}
      />
      {error ? (
        <View style={styles.errorBox}>
          <Ionicons name="alert-circle-outline" size={36} color={C.textHint} />
          <Text style={styles.errorText}>{error}</Text>
          <TouchableOpacity style={styles.btn} onPress={retry}>
            <Text style={styles.btnText}>Try again</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={openElsewhere} disabled={opening}>
            <Text style={styles.link}>{opening ? 'Opening…' : 'Open in another app'}</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <View style={styles.viewer}>
          <WebView
            key={attempt}
            testID="pdf-viewer"
            originWhitelist={['*']}
            source={{ html, baseUrl: BASE }}
            onMessage={onMessage}
            onError={() => setError('The PDF viewer could not load.')}
            setDisplayZoomControls={false}
          />
          {!position ? (
            <View style={styles.loading} pointerEvents="none">
              <ActivityIndicator size="large" color={C.primary} />
              <Text style={styles.loadingText}>Opening at page {citation.open_page}…</Text>
            </View>
          ) : null}
        </View>
      )}
    </View>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  viewer: { flex: 1 },
  loading: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center', gap: 10, backgroundColor: C.bg },
  loadingText: { fontSize: 14, color: C.textSub },
  errorBox: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 32, gap: 14 },
  errorText: { fontSize: 15, color: C.text, textAlign: 'center' },
  btn: { backgroundColor: C.primary, borderRadius: 10, paddingHorizontal: 24, paddingVertical: 11 },
  btnText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  link: { fontSize: 14, fontWeight: '600', color: C.primary },
})
