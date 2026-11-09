import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native'
import { LinearGradient } from 'expo-linear-gradient'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useLecturer } from '../context/LecturerContext'
import { C } from '../theme'

export default function Login({ navigation }) {
  const { login, state } = useLecturer()
  const insets = useSafeAreaInsets()
  const [identifier, setIdentifier] = useState('')
  const [password, setPassword] = useState('')
  const [showPw, setShowPw] = useState(false)
  const [localErr, setLocalErr] = useState('')
  // Administrators sign in with a SmartClass email + password, in the browser only
  const [adminMode, setAdminMode] = useState(false)
  const local = Platform.OS === 'web' && adminMode

  const switchMode = () => {
    setAdminMode(v => !v)
    setIdentifier('')
    setPassword('')
    setLocalErr('')
  }

  const handleLogin = async () => {
    setLocalErr('')
    if (!identifier.trim() || !password) {
      setLocalErr(local ? 'Enter your email and password.' : 'Enter your SPeCTRUM username and password.')
      return
    }
    try {
      await login(identifier, password, { local })
    } catch (e) {
      setLocalErr(e.message || 'Sign-in failed. Please try again.')
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <LinearGradient
        colors={['#EBF2FF', '#F5F6F8']}
        start={{ x: 0, y: 0 }}
        end={{ x: 0.5, y: 1 }}
        style={[styles.flex, { paddingTop: insets.top }]}
      >
        <ScrollView
          contentContainerStyle={styles.scrollContent}
          keyboardShouldPersistTaps="handled"
          showsVerticalScrollIndicator={false}
        >
          {/* Logo top */}
          <View style={styles.topSection}>
            <View style={styles.logoCircle}>
              <Ionicons name="school" size={32} color={C.primary} />
            </View>
            <Text style={styles.appName}>SmartClass</Text>
            <Text style={styles.tagline}>
              Lecturer Portal · University of Malaya{'\n'}Faculty of Computer Science & IT
            </Text>
          </View>

          {/* Form */}
          <View style={styles.formCard}>
            <Text style={styles.welcomeTitle}>Welcome back</Text>
            <Text style={styles.welcomeSub}>
              {local ? 'Administrator sign-in with your SmartClass account' : 'Sign in with your university credentials'}
            </Text>

            {localErr ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{localErr}</Text>
              </View>
            ) : null}

            <Text style={styles.label}>{local ? 'Email address' : 'SPeCTRUM username'}</Text>
            <View style={styles.inputWrap}>
              <Ionicons name={local ? 'mail-outline' : 'person-outline'} size={18} color={C.textHint} style={styles.inputIcon} />
              <TextInput
                testID="login-username"
                style={styles.input}
                value={identifier}
                onChangeText={setIdentifier}
                keyboardType={local ? 'email-address' : 'default'}
                autoCapitalize="none"
                autoCorrect={false}
                autoComplete={local ? 'email' : 'username'}
                placeholder={local ? 'your@um.edu.my' : 'Your SPeCTRUM username'}
                placeholderTextColor={C.textHint}
              />
              {identifier ? (
                <TouchableOpacity onPress={() => setIdentifier('')} style={styles.eyeBtn} accessibilityLabel="Clear username">
                  <Ionicons name="close-circle" size={18} color={C.textHint} />
                </TouchableOpacity>
              ) : null}
            </View>

            <Text style={styles.label}>Password</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="lock-closed-outline" size={18} color={C.textHint} style={styles.inputIcon} />
              <TextInput
                testID="login-password"
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPw}
                autoCapitalize="none"
                autoComplete="password"
                placeholder="Enter password"
                placeholderTextColor={C.textHint}
                onSubmitEditing={handleLogin}
              />
              <TouchableOpacity onPress={() => setShowPw(v => !v)} style={styles.eyeBtn} accessibilityLabel={showPw ? 'Hide password' : 'Show password'}>
                <Ionicons name={showPw ? 'eye-outline' : 'eye-off-outline'} size={18} color={C.textHint} />
              </TouchableOpacity>
            </View>

            <TouchableOpacity
              style={[styles.signInBtn, state.loading && styles.btnDisabled]}
              onPress={handleLogin}
              disabled={state.loading}
            >
              {state.loading ? (
                <ActivityIndicator color="#fff" size="small" />
              ) : (
                <>
                  <Ionicons name="log-in-outline" size={18} color="#fff" style={{ marginRight: 8 }} />
                  <Text style={styles.signInText}>Sign In</Text>
                </>
              )}
            </TouchableOpacity>

            {Platform.OS === 'web' ? (
              <TouchableOpacity onPress={switchMode} style={styles.modeLink} accessibilityRole="button">
                <Text style={styles.modeLinkText}>
                  {local ? 'Lecturer? Sign in with SPeCTRUM' : 'Administrator sign-in'}
                </Text>
              </TouchableOpacity>
            ) : null}

          </View>
        </ScrollView>
      </LinearGradient>
    </KeyboardAvoidingView>
  )
}

const styles = StyleSheet.create({
  flex: { flex: 1 },
  scrollContent: {
    flexGrow: 1,
    justifyContent: 'center',
    padding: 24,
    paddingBottom: 40,
  },
  topSection: {
    alignItems: 'center',
    marginBottom: 32,
  },
  logoCircle: {
    width: 72,
    height: 72,
    borderRadius: 36,
    backgroundColor: C.blueLt,
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  appName: {
    fontSize: 26,
    fontWeight: '800',
    color: C.text,
    letterSpacing: -0.5,
  },
  tagline: {
    fontSize: 13,
    color: C.textSub,
    textAlign: 'center',
    marginTop: 6,
    lineHeight: 20,
  },
  formCard: {
    width: '100%',
    maxWidth: 440,
    alignSelf: 'center',
    backgroundColor: C.card,
    borderRadius: 16,
    padding: 22,
    shadowColor: '#000',
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.08,
    shadowRadius: 8,
    elevation: 3,
  },
  welcomeTitle: {
    fontSize: 20,
    fontWeight: '700',
    color: C.text,
    marginBottom: 4,
  },
  welcomeSub: {
    fontSize: 13,
    color: C.textSub,
    marginBottom: 20,
  },
  errorBox: {
    backgroundColor: C.redLt,
    borderRadius: 8,
    padding: 10,
    marginBottom: 14,
  },
  errorText: {
    fontSize: 13,
    color: C.redDk,
  },
  label: {
    fontSize: 12,
    fontWeight: '700',
    color: C.text,
    marginBottom: 6,
  },
  inputWrap: {
    flexDirection: 'row',
    alignItems: 'center',
    borderWidth: 1.5,
    borderColor: C.border,
    borderRadius: 10,
    backgroundColor: C.bg,
    marginBottom: 14,
    paddingHorizontal: 12,
  },
  inputIcon: {
    marginRight: 8,
  },
  input: {
    flex: 1,
    fontSize: 14,
    color: C.text,
    paddingVertical: 13,
  },
  eyeBtn: {
    padding: 4,
  },
  signInBtn: {
    backgroundColor: C.primary,
    borderRadius: 10,
    paddingVertical: 14,
    flexDirection: 'row',
    alignItems: 'center',
    justifyContent: 'center',
    marginBottom: 14,
  },
  btnDisabled: {
    opacity: 0.65,
  },
  signInText: {
    fontSize: 16,
    fontWeight: '700',
    color: '#fff',
  },
  modeLink: {
    alignSelf: 'center',
    padding: 6,
  },
  modeLinkText: {
    fontSize: 13,
    fontWeight: '600',
    color: C.primary,
  },
})
