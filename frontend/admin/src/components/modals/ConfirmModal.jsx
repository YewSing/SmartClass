import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

export function ConfirmDeleteModal() {
  const { state, dispatch, closeModal, toast } = useAdmin()
  const user = state.users.find(u => u.id === state.selectedUserId)

  if (state.modal?.type !== 'confirmDelete' || !user) return null

  const handleDelete = () => {
    dispatch({ type: 'DELETE_USER', payload: user.id })
    closeModal()
    toast(`Account deleted: ${user.name}`, 'info')
  }

  return (
    <Modal
      title="Confirm Deletion"
      onClose={closeModal}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={closeModal}>Cancel</Button>
          <Button variant="danger" onClick={handleDelete}>Delete Account</Button>
        </>
      }
    >
      <div className="text-center py-2">
        <div className="w-11 h-11 rounded-full bg-red-50 flex items-center justify-center text-xl mx-auto mb-3.5">🗑</div>
        <p className="text-[13.5px] text-text2 leading-relaxed">This will permanently delete the user account and all associated data.</p>
        <p className="text-[12px] text-text3 mt-2">{user.name} — <span className="font-sans">{user.id}</span></p>
      </div>
    </Modal>
  )
}

export function ConfirmRemoveFaceModal() {
  const { state, dispatch, closeModal, toast } = useAdmin()
  const user = state.users.find(u => u.id === state.selectedUserId)

  if (state.modal?.type !== 'confirmRemoveFace' || !user) return null

  const handleRemove = () => {
    dispatch({ type: 'REMOVE_FACE', payload: user.id })
    closeModal()
    toast(`Face data removed for ${user.name.split(' ')[0]} — NFR-01 compliant`, 'info')
  }

  return (
    <Modal
      title="Remove Face Data"
      onClose={closeModal}
      size="sm"
      footer={
        <>
          <Button variant="ghost" onClick={closeModal}>Cancel</Button>
          <Button variant="danger" onClick={handleRemove}>Remove Face Data</Button>
        </>
      }
    >
      <div className="text-center py-2">
        <div className="w-11 h-11 rounded-full bg-orange-50 flex items-center justify-center text-xl mx-auto mb-3.5">⚠</div>
        <p className="text-[13.5px] text-text2 leading-relaxed">This will permanently remove the face recognition embedding. The student will not be detected in attendance sessions until re-enrolled.</p>
        <p className="text-[12px] text-text3 mt-2">{user.name} — <span className="font-sans">{user.id}</span></p>
      </div>
    </Modal>
  )
}
