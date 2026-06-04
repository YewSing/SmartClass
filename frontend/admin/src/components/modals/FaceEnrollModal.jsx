import { useState, useRef, useEffect } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

const MIN_SAMPLES = 3
const MAX_SAMPLES = 5

export default function FaceEnrollModal() {
  const { state, enrollFace, closeModal, toast } = useAdmin()
  const user = state.users.find(u => u.id === state.selectedUserId)
  const isActive = state.modal?.type === 'faceEnroll' && !!user

  const [cameraErr, setCameraErr] = useState(null)
  const [captures, setCaptures] = useState([])   // { id, thumb, blob }
  const [capturing, setCapturing] = useState(false)
  const [saving, setSaving] = useState(false)
  const [saveErr, setSaveErr] = useState(null)
  const [done, setDone] = useState(false)

  const videoRef = useRef(null)
  const canvasRef = useRef(null)
  const streamRef = useRef(null)
  const nextIdRef = useRef(0)

  useEffect(() => {
    if (!isActive) return
    let mounted = true
    setCameraErr(null)
    setCaptures([])
    setSaveErr(null)
    setDone(false)
    nextIdRef.current = 0

    navigator.mediaDevices.getUserMedia({ video: { facingMode: 'user' } })
      .then(stream => {
        if (!mounted) { stream.getTracks().forEach(t => t.stop()); return }
        streamRef.current = stream
        if (videoRef.current) videoRef.current.srcObject = stream
      })
      .catch(() => {
        if (mounted) setCameraErr('Camera access denied. Please allow camera permissions in your browser and try again.')
      })

    return () => {
      mounted = false
      streamRef.current?.getTracks().forEach(t => t.stop())
      streamRef.current = null
    }
  }, [isActive])

  if (!isActive) return null

  const handleClose = () => {
    streamRef.current?.getTracks().forEach(t => t.stop())
    streamRef.current = null
    closeModal()
  }

  const captureFrame = async () => {
    if (!videoRef.current || !canvasRef.current || capturing || captures.length >= MAX_SAMPLES) return
    setCapturing(true)

    const video = videoRef.current
    const canvas = canvasRef.current
    canvas.width = video.videoWidth || 640
    canvas.height = video.videoHeight || 480
    canvas.getContext('2d').drawImage(video, 0, 0)

    const thumb = canvas.toDataURL('image/jpeg', 0.7)
    const blob = await new Promise(resolve => canvas.toBlob(resolve, 'image/jpeg', 0.9))
    const id = nextIdRef.current++

    setCaptures(prev => [...prev, { id, thumb, blob }])
    setCapturing(false)
  }

  const remove = (id) => setCaptures(prev => prev.filter(c => c.id !== id))

  const handleSave = async () => {
    setSaving(true)
    setSaveErr(null)
    try {
      await enrollFace(user.id, captures.map(c => c.blob))
      setDone(true)
      toast(`Face data enrolled for ${user.name.split(' ')[0]} — ${captures.length} samples`, 'success')
    } catch (e) {
      const msg = e.message ?? ''
      if (/503|model not loaded/i.test(msg)) {
        setSaveErr('Enrolment failed — face recognition backend is unavailable. No data was saved. Please try again.')
      } else if (/422|no face/i.test(msg)) {
        setSaveErr('No face detected in any of the captured samples. Please retake with the student facing the camera clearly.')
      } else {
        setSaveErr(msg)
      }
    } finally {
      setSaving(false)
    }
  }

  if (done) {
    return (
      <Modal title="Enrolment Complete" onClose={handleClose} size="md"
        footer={<Button variant="primary" onClick={handleClose}>Done</Button>}
      >
        <div className="text-center py-4">
          <div className="w-12 h-12 rounded-full bg-sc-green-lt flex items-center justify-center mx-auto mb-3">
            <i className="fa-solid fa-circle-check text-sc-green text-2xl" />
          </div>
          <p className="text-[14px] font-semibold text-text1">Face data enrolled successfully.</p>
          <p className="text-[13px] text-text2 mt-1">{captures.length} sample{captures.length !== 1 ? 's' : ''} captured for {user.name.split(' ')[0]}.</p>
          <p className="text-[11px] text-text3 mt-3 leading-relaxed">NFR-01: All captured frames were discarded by the server immediately after embedding extraction.</p>
        </div>
      </Modal>
    )
  }

  return (
    <Modal
      title="Face Data Enrolment"
      subtitle={`UC-08 — Live webcam capture · ${user.name}`}
      onClose={handleClose}
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={handleClose}>Cancel</Button>
          <Button variant="primary" onClick={handleSave} disabled={captures.length < MIN_SAMPLES || saving}>
            {saving
              ? 'Enrolling…'
              : `Save Enrolment${captures.length > 0 ? ` (${captures.length} sample${captures.length !== 1 ? 's' : ''})` : ''}`}
          </Button>
        </>
      }
    >
      {cameraErr ? (
        <div className="rounded-xl border border-[#f5c6c6] bg-[#fef2f2] p-4 flex items-start gap-3 text-[13px] text-[#b91c1c]">
          <i className="fa-solid fa-circle-exclamation mt-0.5 shrink-0" />
          <span>{cameraErr}</span>
        </div>
      ) : (
        <div className="space-y-4">
          {/* Live feed */}
          <div className="relative bg-black rounded-xl overflow-hidden" style={{ aspectRatio: '16/9' }}>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              className="w-full h-full object-cover"
              style={{ transform: 'scaleX(-1)' }}
            />
            <span className="absolute bottom-2.5 left-3 bg-black/55 text-white text-[11px] px-2 py-0.5 rounded-full">
              Live
            </span>
          </div>

          {/* Instructions + capture button */}
          <div className="text-center space-y-3">
            <p className="text-[12.5px] text-text2 leading-relaxed">
              Ask the student to look slightly <strong className="text-text1">left</strong>,{' '}
              <strong className="text-text1">right</strong>, and{' '}
              <strong className="text-text1">straight ahead</strong>.
              Capture {MIN_SAMPLES}–{MAX_SAMPLES} clear samples.
            </p>
            <Button
              variant="primary"
              onClick={captureFrame}
              disabled={capturing || captures.length >= MAX_SAMPLES}
              className="px-8"
            >
              <i className="fa-solid fa-camera mr-2" />
              {capturing ? 'Capturing…' : captures.length >= MAX_SAMPLES ? 'Maximum reached' : 'Capture Sample'}
            </Button>
          </div>

          {/* Save error */}
          {saveErr && (
            <div className="rounded-xl border border-[#f5c6c6] bg-[#fef2f2] p-3.5 flex items-start gap-2.5 text-[12.5px] text-[#b91c1c]">
              <i className="fa-solid fa-circle-exclamation mt-0.5 shrink-0" />
              <span>{saveErr}</span>
            </div>
          )}

          {/* Thumbnail strip */}
          {captures.length > 0 && (
            <div className="space-y-2">
              <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text3">
                Captured samples — {captures.length} / {MAX_SAMPLES}
              </p>
              <div className="flex flex-wrap gap-3">
                {captures.map(cap => (
                  <div key={cap.id} className="flex flex-col items-center gap-1.5">
                    <div className="relative">
                      <img
                        src={cap.thumb}
                        alt="capture"
                        className="w-[68px] h-[68px] object-cover rounded-lg border-2 border-sc-green"
                      />
                      <span className="absolute -top-1.5 -right-1.5 w-[18px] h-[18px] rounded-full bg-sc-green text-[9px] font-bold flex items-center justify-center text-white">
                        ✓
                      </span>
                    </div>
                    <button
                      onClick={() => remove(cap.id)}
                      className="text-[10.5px] text-text3 hover:text-sc-red leading-none transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Progress hint */}
          <p className="text-[11.5px] text-text3 text-center">
            {captures.length === 0
              ? `Capture at least ${MIN_SAMPLES} samples to enable Save.`
              : captures.length < MIN_SAMPLES
                ? `${MIN_SAMPLES - captures.length} more sample${MIN_SAMPLES - captures.length !== 1 ? 's' : ''} needed.`
                : 'Minimum reached — click "Save Enrolment" or add more samples.'}
          </p>

          <p className="text-[11px] text-text3 text-center leading-relaxed border-t border-border pt-3">
            NFR-01: All captured frames are discarded by the server immediately after embedding extraction.
          </p>
        </div>
      )}

      <canvas ref={canvasRef} className="hidden" />
    </Modal>
  )
}
