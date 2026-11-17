import 'react-native-url-polyfill/auto'
import { registerRootComponent } from 'expo'
import { useEffect, useState } from 'react'
import { Platform, View, ActivityIndicator } from 'react-native'
import { SafeAreaProvider } from 'react-native-safe-area-context'
import { StudentProvider } from './src/context/StudentContext'
import AppNavigator from './src/navigation/AppNavigator'
import { initStorage } from './src/services/client'
import { C } from './src/theme'
import PhoneShell from './src/components/PhoneShell'

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

  const inner = (
    <StudentProvider>
      <AppNavigator />
    </StudentProvider>
  )

  return (
    <SafeAreaProvider>
      {Platform.OS === 'web' ? <PhoneShell>{inner}</PhoneShell> : inner}
    </SafeAreaProvider>
  )
}

registerRootComponent(App)
