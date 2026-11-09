import { useRef, useState } from 'react'
import {
  View, Text, TouchableOpacity, ScrollView, StyleSheet, ActivityIndicator, Image, useWindowDimensions,
} from 'react-native'
import { CameraView, useCameraPermissions } from 'expo-camera'
import { Ionicons } from '@expo/vector-icons'
import { useSafeAreaInsets } from 'react-native-safe-area-context'
import Topbar from '../components/Topbar'
import { useStudent } from '../context/StudentContext'
import { submitFaceEnrolment } from '../services/api'
import { SELFIE_STEPS, CARD_STEP, TOTAL_STEPS, retakeFromError } from '../services/faceEnrolment'
import { C } from '../theme'

const CARD_RATIO = 85.6 / 54 // ID-1 card (matric card) width / height
const CARD_STEP_INDEX = SELFIE_STEPS.length

// Guided capture: 3 selfies at different angles, then the matric card (FR-110)
export default function FaceCapture({ navigation }) {
  const { showToast } = useStudent()
  const [permission, requestPermission] = useCameraPermissions()
  const [step, setStep] = useState(0)            // 0..2 selfies, 3 card
  const [selfies, setSelfies] = useState([])
  const [card, setCard] = useState(null)
  const [phase, setPhase] = useState('camera')   // camera | review | submitting | retake
  const [retake, setRetake] = useState(null)     // from retakeFromError

  const goTo = (s) => { setStep(s); setPhase('camera') }

  const onPhoto = (photo) => {
    if (step < CARD_STEP_INDEX) {
      const next = [...selfies.slice(0, step), photo]
      setSelfies(next)
      // After a selfie retake the card is kept, so go straight back to review
      if (step + 1 < CARD_STEP_INDEX) goTo(step + 1)
      else if (card) setPhase('review')
      else goTo(CARD_STEP_INDEX)
    } else {
      setCard(photo)
      setPhase('review')
    }
  }

  const submit = async (submitAnyway = false) => {
    setPhase('submitting')
    try {
      const result = await submitFaceEnrolment(selfies, card, submitAnyway)
      showToast(result.status === 'active'
        ? 'Your face is enrolled.'
        : 'Sent to a lecturer for review.', 'success')
      navigation.navigate('FaceEnrolment')
    } catch (e) {
      const r = retakeFromError(e)
      if (r) {
        setRetake(r)
        setPhase('retake')
        return
      }
      showToast(e.message, 'error')
      if (e.status === 409) navigation.navigate('FaceEnrolment')
      else setPhase('review')
    }
  }

  const doRetake = () => {
    if (retake?.retake === 'card') {
      setCard(null)
      goTo(CARD_STEP_INDEX)
    } else {
      setSelfies([])
      if (retake?.retake === 'all') setCard(null)
      goTo(0)
    }
  }

  const title = phase === 'camera' ? `Step ${step + 1} of ${TOTAL_STEPS}` : 'Face enrolment'

  if (!permission) {
    return <View style={styles.screen}><ActivityIndicator style={styles.flex} color={C.primary} /></View>
  }
  if (!permission.granted) {
    return (
      <View style={styles.screen}>
        <Topbar title="Face enrolment" onBack={() => navigation.goBack()} />
        <View style={styles.centerBox}>
          <Ionicons name="camera-outline" size={40} color={C.primary} />
          <Text style={styles.centerText}>SmartClass needs the camera to take your selfies and card photo.</Text>
          <TouchableOpacity style={styles.primaryBtn} onPress={requestPermission}>
            <Text style={styles.primaryText}>Allow camera</Text>
          </TouchableOpacity>
        </View>
      </View>
    )
  }

  return (
    <View style={styles.screen}>
      <Topbar title={title} sub={phase === 'camera' ? 'Take the photos in good light' : undefined}
        onBack={() => navigation.goBack()} />
      {phase === 'camera' ? (
        <CaptureStep step={step} onPhoto={onPhoto} onError={(m) => showToast(m, 'error')} />
      ) : phase === 'retake' ? (
        <RetakeView retake={retake} onRetake={doRetake} onSubmitAnyway={() => submit(true)} />
      ) : (
        <ReviewView
          selfies={selfies}
          card={card}
          submitting={phase === 'submitting'}
          onRetakeSelfies={() => { setSelfies([]); goTo(0) }}
          onRetakeCard={() => goTo(CARD_STEP_INDEX)}
          onSubmit={() => submit(false)}
        />
      )}
    </View>
  )
}

// One camera step with its guide: an oval for selfies, a card outline for the matric card
function CaptureStep({ step, onPhoto, onError }) {
  const camera = useRef(null)
  const [ready, setReady] = useState(false)
  const [busy, setBusy] = useState(false)
  const { width } = useWindowDimensions()
  const { bottom } = useSafeAreaInsets()
  const isCard = step === CARD_STEP_INDEX
  const info = isCard ? CARD_STEP : SELFIE_STEPS[step]

  const shoot = async () => {
    if (!camera.current || busy) return
    setBusy(true)
    try {
      const photo = await camera.current.takePictureAsync({ quality: 0.8 })
      onPhoto({ uri: photo.uri })
    } catch (e) {
      onError(`Couldn't take the photo: ${e.message}`)
    } finally {
      setBusy(false)
    }
  }

  const guideW = width * (isCard ? 0.86 : 0.62)
  const guideH = isCard ? guideW / CARD_RATIO : guideW * 1.3

  return (
    <View style={styles.flex}>
      <View style={styles.cameraWrap}>
        <CameraView
          key={isCard ? 'back' : 'front'}
          ref={camera}
          style={StyleSheet.absoluteFill}
          facing={isCard ? 'back' : 'front'}
          onCameraReady={() => setReady(true)}
        />
        <View style={styles.guideLayer} pointerEvents="none">
          <View
            testID={isCard ? 'card-guide' : 'selfie-guide'}
            style={[
              styles.guide,
              { width: guideW, height: guideH, borderRadius: isCard ? 14 : guideW / 2 },
            ]}
          />
        </View>
      </View>
      <View style={[styles.captureBar, { paddingBottom: 16 + bottom }]}>
        <Text style={styles.stepTitle}>{info.title}</Text>
        <Text style={styles.stepHint}>{info.hint}</Text>
        <TouchableOpacity
          testID="capture-button"
          accessibilityLabel="Take photo"
          style={[styles.shutter, (!ready || busy) && styles.disabled]}
          onPress={shoot}
          disabled={!ready || busy}
        >
          {busy ? <ActivityIndicator color={C.primary} /> : <View style={styles.shutterInner} />}
        </TouchableOpacity>
      </View>
    </View>
  )
}

function ReviewView({ selfies, card, submitting, onRetakeSelfies, onRetakeCard, onSubmit }) {
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <Text style={styles.sectionLabel}>Selfies</Text>
      <View style={styles.thumbRow}>
        {selfies.map((p, i) => <Image key={p.uri} source={{ uri: p.uri }} style={styles.selfieThumb}
          accessibilityLabel={`Selfie ${i + 1}`} />)}
      </View>
      <TouchableOpacity onPress={onRetakeSelfies} disabled={submitting}>
        <Text style={styles.link}>Retake selfies</Text>
      </TouchableOpacity>

      <Text style={styles.sectionLabel}>Matric card</Text>
      {card ? <Image source={{ uri: card.uri }} style={styles.cardThumb} accessibilityLabel="Card photo" /> : null}
      <TouchableOpacity onPress={onRetakeCard} disabled={submitting}>
        <Text style={styles.link}>Retake card photo</Text>
      </TouchableOpacity>

      <Text style={styles.note}>
        We check that the selfies match the photo on your card and that the matric number is yours.
        The photos are deleted after the check.
      </Text>
      <TouchableOpacity style={[styles.primaryBtn, submitting && styles.disabled]} onPress={onSubmit}
        disabled={submitting}>
        {submitting ? (
          <>
            <ActivityIndicator color="#fff" size="small" style={{ marginRight: 8 }} />
            <Text style={styles.primaryText}>Checking your photos…</Text>
          </>
        ) : <Text style={styles.primaryText}>Submit</Text>}
      </TouchableOpacity>
    </ScrollView>
  )
}

// A 422 from the server: the specific retake message, a Retake button, and "submit anyway" when allowed
function RetakeView({ retake, onRetake, onSubmitAnyway }) {
  const what = retake?.retake === 'card' ? 'card photo' : retake?.retake === 'selfies' ? 'selfies' : 'photos'
  return (
    <ScrollView contentContainerStyle={styles.content}>
      <View style={styles.retakeBox}>
        <Ionicons name="alert-circle-outline" size={28} color={C.orangeDk} />
        <Text style={styles.retakeTitle}>Please retake your {what}</Text>
        <Text style={styles.retakeText}>{retake?.message}</Text>
      </View>
      <TouchableOpacity style={styles.primaryBtn} onPress={onRetake}>
        <Ionicons name="camera-outline" size={18} color="#fff" style={{ marginRight: 8 }} />
        <Text style={styles.primaryText}>Retake</Text>
      </TouchableOpacity>
      {retake?.canSubmitAnyway ? (
        <>
          <TouchableOpacity style={styles.secondaryBtn} onPress={onSubmitAnyway}>
            <Text style={styles.secondaryText}>Submit anyway</Text>
          </TouchableOpacity>
          <Text style={styles.note}>
            A lecturer of one of your courses will check your photos by hand. This can take a while.
          </Text>
        </>
      ) : null}
    </ScrollView>
  )
}

const styles = StyleSheet.create({
  screen: { flex: 1, backgroundColor: C.bg },
  flex: { flex: 1 },
  cameraWrap: { flex: 1, backgroundColor: '#000', overflow: 'hidden' },
  guideLayer: { ...StyleSheet.absoluteFillObject, alignItems: 'center', justifyContent: 'center' },
  guide: { borderWidth: 3, borderColor: '#fff', borderStyle: 'dashed' },
  captureBar: { backgroundColor: C.card, paddingTop: 14, paddingHorizontal: 16, alignItems: 'center', gap: 4 },
  stepTitle: { fontSize: 16, fontWeight: '700', color: C.text, textAlign: 'center' },
  stepHint: { fontSize: 13, color: C.textSub, textAlign: 'center', marginBottom: 10 },
  shutter: {
    width: 68, height: 68, borderRadius: 34, borderWidth: 4, borderColor: C.primary,
    alignItems: 'center', justifyContent: 'center',
  },
  shutterInner: { width: 50, height: 50, borderRadius: 25, backgroundColor: C.primary },
  content: { padding: 16, paddingBottom: 32, gap: 10 },
  sectionLabel: {
    fontSize: 12, fontWeight: '700', color: C.textSub, textTransform: 'uppercase', letterSpacing: 0.5,
  },
  thumbRow: { flexDirection: 'row', gap: 8 },
  selfieThumb: { flex: 1, aspectRatio: 3 / 4, borderRadius: 8, backgroundColor: C.gray100 },
  cardThumb: { width: '100%', aspectRatio: 4 / 3, borderRadius: 8, backgroundColor: C.gray100 },
  link: { color: C.primary, fontSize: 14, fontWeight: '600' },
  note: { fontSize: 13, color: C.textSub, lineHeight: 19 },
  primaryBtn: {
    flexDirection: 'row', alignItems: 'center', justifyContent: 'center',
    backgroundColor: C.primary, borderRadius: 10, paddingVertical: 14, paddingHorizontal: 20,
  },
  primaryText: { color: '#fff', fontSize: 15, fontWeight: '700' },
  secondaryBtn: {
    borderWidth: 1, borderColor: C.primary, borderRadius: 10, paddingVertical: 12, alignItems: 'center',
  },
  secondaryText: { color: C.primary, fontSize: 15, fontWeight: '700' },
  disabled: { opacity: 0.5 },
  centerBox: { flex: 1, alignItems: 'center', justifyContent: 'center', padding: 24, gap: 14 },
  centerText: { fontSize: 14, color: C.textSub, textAlign: 'center' },
  retakeBox: {
    backgroundColor: C.orangeLt, borderRadius: 12, padding: 16, alignItems: 'center', gap: 6,
    borderWidth: 1, borderColor: '#FED7AA',
  },
  retakeTitle: { fontSize: 16, fontWeight: '700', color: C.orangeDk },
  retakeText: { fontSize: 14, color: C.text, textAlign: 'center', lineHeight: 20 },
})
