import 'react-native-url-polyfill/auto'
import { registerRootComponent } from 'expo'
import { useEffect, useState } from 'react'
import { View, ActivityIndicator } from 'react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { LecturerProvider } from './src/context/LecturerContext'
import AppNavigator from './src/navigation/AppNavigator'
import { initStorage } from './src/services/client'
import { C } from './src/theme'

function App() {
  const [ready, setReady] = useState(false)

  useEffect(() => {
    initStorage().then(() => setReady(true))
  }, [])

  if (!ready) {
    return (
      <View style={{ flex: 1, alignItems: 'center', justifyContent: 'center', backgroundColor: C.bg }}>
        <ActivityIndicator size="large" color={C.primary} />
      </View>
    )
  }

  return (
    <SafeAreaProvider>
      <LecturerProvider>
        <AppNavigator />
      </LecturerProvider>
    </SafeAreaProvider>
  )
}

registerRootComponent(App)
