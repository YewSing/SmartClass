import { useState } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

export function ConfirmRemoveOccurrenceModal() {
  const { state, openModal, closeModal, toggleOccurrenceEnrollment, toast } = useAdmin()
  const [loading, setLoading] = useState(false)

  if (state.modal?.type !== 'confirmRemoveOccurrence') return null
  const { occObj, userId, userRole, userName } = state.modal.data

  const label = occObj.type === 'LECTURE' ? 'Lecture' : (occObj.label ?? 'Tutorial')

  const courseCode = occObj.course_code ?? occObj.code
  const courseName = occObj.course_name ?? occObj.name

  const handleRemove = async () => {
    setLoading(true)
    try {
      await toggleOccurrenceEnrollment(userId, userRole, occObj, false)
      openModal('studentProfile')
      toast(`Removed from ${courseCode} ${label}`, 'info')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Remove from Class"
      onClose={() => openModal('studentProfile')}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={() => openModal('studentProfile')}>Cancel</Button>
          <Button variant="danger" onClick={handleRemove} disabled={loading}>
            {loading ? 'Removing…' : 'Remove'}
          </Button>
        </>
      }
    >
      <div className="text-center py-2">
        <div className="w-11 h-11 rounded-full bg-red-50 flex items-center justify-center text-xl mx-auto mb-3.5">🗑</div>
        <p className="text-[13.5px] text-text2 leading-relaxed">
          Remove <strong>{userName}</strong> from this class occurrence?
        </p>
        <div className="mt-3 px-3 py-2.5 rounded-lg bg-surface2 border border-border text-left space-y-1">
          <p className="text-[13px] font-semibold text-text1">
            <span className="font-sans text-accent">{courseCode}</span> — {courseName}
          </p>
          <p className="text-[12px] text-text3">
            {label} · {occObj.day_of_week} · {occObj.start_time}–{occObj.end_time}
          </p>
        </div>
      </div>
    </Modal>
  )
}

export function ConfirmDeleteModal() {
  const { state, deactivateUser, closeModal, toast } = useAdmin()
  const [loading, setLoading] = useState(false)
  const user = state.users.find(u => u.id === state.selectedUserId)

  if (state.modal?.type !== 'confirmDelete' || !user) return null

  const handleDelete = async () => {
    setLoading(true)
    try {
      await deactivateUser(user.id)
      closeModal()
      toast(`Account deactivated: ${user.name}`, 'info')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Deactivate Account"
      onClose={closeModal}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={closeModal}>Cancel</Button>
          <Button variant="danger" onClick={handleDelete} disabled={loading}>
            {loading ? 'Deactivating…' : 'Deactivate Account'}
          </Button>
        </>
      }
    >
      <div className="text-center py-2">
        <div className="w-11 h-11 rounded-full bg-red-50 flex items-center justify-center text-xl mx-auto mb-3.5">🚫</div>
        <p className="text-[13.5px] text-text2 leading-relaxed">This will deactivate the account. The user will no longer be able to sign in.</p>
        <p className="text-[12px] text-text3 mt-2">{user.name} — <span className="font-sans">{user.matric ?? user.id}</span></p>
      </div>
    </Modal>
  )
}

export function ConfirmRemoveFaceModal() {
  const { state, removeFace, closeModal, toast } = useAdmin()
  const [loading, setLoading] = useState(false)
  const user = state.users.find(u => u.id === state.selectedUserId)

  if (state.modal?.type !== 'confirmRemoveFace' || !user) return null

  const handleRemove = async () => {
    setLoading(true)
    try {
      await removeFace(user.id)
      closeModal()
      toast(`Face data removed for ${user.name.split(' ')[0]}`, 'info')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Remove Face Data"
      onClose={closeModal}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={closeModal}>Cancel</Button>
          <Button variant="danger" onClick={handleRemove} disabled={loading}>
            {loading ? 'Removing…' : 'Remove Face Data'}
          </Button>
        </>
      }
    >
      <div className="text-center py-2">
        <div className="w-11 h-11 rounded-full bg-orange-50 flex items-center justify-center text-xl mx-auto mb-3.5">⚠</div>
        <p className="text-[13.5px] text-text2 leading-relaxed">
          This will permanently remove <strong>{user.name.split(' ')[0]}</strong>'s face data.
          They will not be recognised until re-enrolled.
        </p>
        <p className="text-[12px] text-text3 mt-2">{user.name} — <span className="font-sans">{user.matric ?? user.id}</span></p>
      </div>
    </Modal>
  )
}
