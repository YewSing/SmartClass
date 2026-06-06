import { useState } from 'react'
import {
  View, Text, TextInput, TouchableOpacity, ScrollView, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
} from 'react-native'
import { LinearGradient } from 'expo-linear-gradient'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import { useStudent } from '../context/StudentContext'
import { C } from '../theme'

export default function Login() {
  const { login, state } = useStudent()
  const insets = useSafeAreaInsets()
  const [email, setEmail] = useState('23004001@siswa.um.edu.my')
  const [password, setPassword] = useState('Student@1234')
  const [showPw, setShowPw] = useState(false)
  const [localErr, setLocalErr] = useState('')

  const handleLogin = async () => {
    setLocalErr('')
    try {
      await login(email, password)
    } catch (e) {
      setLocalErr(e.message || 'Invalid credentials')
    }
  }

  return (
    <KeyboardAvoidingView
      style={styles.flex}
      behavior={Platform.OS === 'ios' ? 'padding' : 'height'}
    >
      <LinearGradient
        colors={['#E5F3FF', '#F5F6F8']}
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
              Student Portal · University of Malaya{'\n'}Faculty of Computer Science & IT
            </Text>
          </View>

          {/* Form */}
          <View style={styles.formCard}>
            <Text style={styles.welcomeTitle}>Welcome back</Text>
            <Text style={styles.welcomeSub}>Sign in with your student credentials</Text>

            {localErr ? (
              <View style={styles.errorBox}>
                <Text style={styles.errorText}>{localErr}</Text>
              </View>
            ) : null}

            <Text style={styles.label}>Matric email</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="mail-outline" size={18} color={C.textHint} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                value={email}
                onChangeText={setEmail}
                keyboardType="email-address"
                autoCapitalize="none"
                placeholder="your@siswa.um.edu.my"
                placeholderTextColor={C.textHint}
              />
              {email ? (
                <TouchableOpacity onPress={() => setEmail('')} style={styles.eyeBtn}>
                  <Ionicons name="close-circle" size={18} color={C.textHint} />
                </TouchableOpacity>
              ) : null}
            </View>

            <Text style={styles.label}>Password</Text>
            <View style={styles.inputWrap}>
              <Ionicons name="lock-closed-outline" size={18} color={C.textHint} style={styles.inputIcon} />
              <TextInput
                style={styles.input}
                value={password}
                onChangeText={setPassword}
                secureTextEntry={!showPw}
                placeholder="Enter password"
                placeholderTextColor={C.textHint}
              />
              <TouchableOpacity onPress={() => setShowPw(v => !v)} style={styles.eyeBtn}>
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
})
