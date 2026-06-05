import { useState } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

const DEPTS = ['Faculty of Computer Science & IT', 'Department of Software Engineering', 'Department of Artificial Intelligence']

const emptyForm = {
  name: '', email: '', matric: '', staffId: '', password: '',
  role: 'Student', phone: '', status: 'Active', dept: DEPTS[0],
  programme: '', faculty: 'FCSIT, University of Malaya', yearSem: '',
}

export default function CreateUserModal() {
  const { state, createUser, closeModal, toast } = useAdmin()
  const [form, setForm] = useState(emptyForm)
  const [loading, setLoading] = useState(false)

  if (state.modal?.type !== 'createUser') return null

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = async () => {
    if (!form.name || !form.email || !form.password) {
      toast('Name, email, and password are required', 'error')
      return
    }
    if (form.role === 'Student' && !form.matric) {
      toast('Matric number is required for students', 'error')
      return
    }
    if (form.role === 'Lecturer' && !form.staffId) {
      toast('Staff ID is required for lecturers', 'error')
      return
    }

    setLoading(true)
    try {
      const body = {
        name: form.name,
        email: form.email,
        password: form.password,
        role: form.role.toLowerCase(),
        phone: form.phone || null,
        ...(form.role === 'Student' ? {
          matric_no: form.matric,
          programme: form.programme || null,
          faculty: form.faculty || null,
          year_sem: form.yearSem || null,
        } : {}),
        ...(form.role === 'Lecturer' ? {
          staff_id: form.staffId,
          dept: form.dept || null,
        } : {}),
      }
      await createUser(body)
      closeModal()
      setForm(emptyForm)
      toast(`Account created: ${form.name}`, 'success')
    } catch (e) {
      toast(e.message, 'error')
    } finally {
      setLoading(false)
    }
  }

  return (
    <Modal
      title="Create User Account"
      subtitle="All accounts are admin-created"
      onClose={() => { closeModal(); setForm(emptyForm) }}
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={() => { closeModal(); setForm(emptyForm) }}>Cancel</Button>
          <Button variant="primary" onClick={handleSave} disabled={loading}>
            {loading ? 'Creating…' : 'Create Account'}
          </Button>
        </>
      }
    >
      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text3 mb-3">Account Details</p>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Full Name" required>
          <input placeholder="e.g. Ahmad Fariz bin Hassan" value={form.name} onChange={e => set('name', e.target.value)} />
        </Field>
        <Field label="Email" required>
          <input type="email" placeholder="e.g. u2024001@siswa.um.edu.my" value={form.email} onChange={e => set('email', e.target.value)} />
        </Field>
        <Field label="Password" required>
          <input type="password" placeholder="Temporary password" value={form.password} onChange={e => set('password', e.target.value)} />
        </Field>
        <Field label="Role" required>
          <select value={form.role} onChange={e => set('role', e.target.value)}>
            <option>Student</option>
            <option>Lecturer</option>
            <option>Admin</option>
          </select>
        </Field>
        {form.role === 'Student' && (
          <Field label="Matric No." required>
            <input placeholder="e.g. U2024001" value={form.matric} onChange={e => set('matric', e.target.value)} />
          </Field>
        )}
        {form.role === 'Lecturer' && (
          <Field label="Staff ID" required>
            <input placeholder="e.g. WL2019-0047" value={form.staffId} onChange={e => set('staffId', e.target.value)} />
          </Field>
        )}
        <Field label="Phone Number">
          <input type="tel" placeholder="+60123456789" value={form.phone} onChange={e => set('phone', e.target.value)} />
        </Field>
        {form.role === 'Lecturer' && (
          <Field label="Department">
            <select value={form.dept} onChange={e => set('dept', e.target.value)}>
              {DEPTS.map(d => <option key={d}>{d}</option>)}
            </select>
          </Field>
        )}
      </div>
    </Modal>
  )
}

function Field({ label, required, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[12px] font-medium text-text2">
        {label}{required && <span className="text-sc-red"> *</span>}
      </label>
      <div className="[&_input]:w-full [&_select]:w-full [&_input]:bg-surface2 [&_select]:bg-surface2 [&_input]:border [&_select]:border [&_input]:border-border [&_select]:border-border [&_input]:rounded-lg [&_select]:rounded-lg [&_input]:px-3 [&_select]:px-3 [&_input]:py-2 [&_select]:py-2 [&_input]:text-[13.5px] [&_select]:text-[13.5px] [&_input]:text-text1 [&_select]:text-text2 [&_input]:outline-none [&_select]:outline-none [&_input:focus]:border-accent [&_select:focus]:border-accent">
        {children}
      </div>
    </div>
  )
}
