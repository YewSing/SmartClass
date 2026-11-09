import { useEffect, useState } from 'react'
import { View, Image, Text, ActivityIndicator, Platform, StyleSheet } from 'react-native'
import { fetchFaceImageUri } from '../services/api'
import { C } from '../theme'

// An image from an API path that needs the signed-in token (face review photos, NFR-01: never cached).
// It is fetched with the token and shown from memory, so nothing is written to an image cache.
export default function AuthImage({ path, style, testID, accessibilityLabel }) {
  const web = Platform.OS === 'web'
  const [uri, setUri] = useState(null)
  const [failed, setFailed] = useState(false)

  useEffect(() => {
    let url = null
    let gone = false
    setUri(null)
    setFailed(false)
    fetchFaceImageUri(path, { web })
      .then(u => {
        if (gone) { if (web) URL.revokeObjectURL(u); return }
        url = u
        setUri(u)
      })
      .catch(() => { if (!gone) setFailed(true) })
    return () => { gone = true; if (web && url) URL.revokeObjectURL(url) }
  }, [path, web])

  if (failed || !uri) {
    return (
      <View style={[style, styles.placeholder]}>
        {failed
          ? <Text style={styles.failText}>Couldn't load photo</Text>
          : <ActivityIndicator color={C.primary} />}
      </View>
    )
  }
  return (
    <Image
      source={{ uri }}
      style={style}
      resizeMode="contain"
      testID={testID}
      accessibilityLabel={accessibilityLabel}
      onError={() => setFailed(true)}
    />
  )
}

const styles = StyleSheet.create({
  placeholder: { alignItems: 'center', justifyContent: 'center', backgroundColor: C.gray100 },
  failText: { fontSize: 11, color: C.textHint, textAlign: 'center', padding: 4 },
})
