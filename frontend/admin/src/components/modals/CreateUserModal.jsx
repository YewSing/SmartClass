import { useState } from 'react'
import { useAdmin } from '../../context/AdminContext'
import Modal from '../ui/Modal'
import Button from '../ui/Button'

const CLASSES = ['WIA2005 — Software Engineering', 'WIA2004 — Algorithm Design', 'WIA2006 — Database Systems', 'WIA3001 — AI Fundamentals']
const DEPTS = ['Faculty of Computer Science & IT', 'Department of Software Engineering', 'Department of Artificial Intelligence']

const emptyForm = { name: '', email: '', matric: '', role: 'Student', phone: '', status: 'Active', dept: DEPTS[0] }

export default function CreateUserModal() {
  const { state, dispatch, closeModal, toast } = useAdmin()
  const [form, setForm] = useState(emptyForm)

  if (state.modal?.type !== 'createUser') return null

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }))

  const handleSave = () => {
    if (!form.name || !form.email || !form.matric) {
      toast('Please fill in all required fields', 'error')
      return
    }
    if (state.users.find(u => u.id === form.matric || u.email === form.email)) {
      toast('Duplicate Matric ID or email — FR-057 violation', 'error')
      return
    }
    dispatch({ type: 'CREATE_USER', payload: { id: form.matric, name: form.name, email: form.email, phone: form.phone || '—', role: form.role, status: form.status, dept: form.dept } })
    closeModal()
    setForm(emptyForm)
    toast(`Account created: ${form.name}`, 'success')
  }

  return (
    <Modal
      title="Create User Account"
      subtitle="All accounts are admin-created (UC-29)"
      onClose={() => { closeModal(); setForm(emptyForm) }}
      size="lg"
      footer={
        <>
          <Button variant="ghost" onClick={() => { closeModal(); setForm(emptyForm) }}>Cancel</Button>
          <Button variant="primary" onClick={handleSave}>Create Account</Button>
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
        <Field label="Matric ID / Staff No." required>
          <input placeholder="e.g. U2024001" value={form.matric} onChange={e => set('matric', e.target.value)} />
        </Field>
        <Field label="Role" required>
          <select value={form.role} onChange={e => set('role', e.target.value)}>
            <option>Student</option>
            <option>Lecturer</option>
            <option>Admin</option>
          </select>
        </Field>
        <Field label="Phone Number">
          <input type="tel" placeholder="+60123456789" value={form.phone} onChange={e => set('phone', e.target.value)} />
        </Field>
        <Field label="Status">
          <select value={form.status} onChange={e => set('status', e.target.value)}>
            <option>Active</option>
            <option>Inactive</option>
          </select>
        </Field>
      </div>

      <hr className="border-border my-4" />

      <p className="text-[11px] font-semibold uppercase tracking-[0.08em] text-text3 mb-3">Class Assignment</p>
      <div className="grid grid-cols-2 gap-3.5">
        <Field label="Assign Classes" hint="Hold Ctrl/⌘ to select multiple">
          <select multiple className="h-24">{CLASSES.map(c => <option key={c}>{c}</option>)}</select>
        </Field>
        <Field label="Department">
          <select value={form.dept} onChange={e => set('dept', e.target.value)}>
            {DEPTS.map(d => <option key={d}>{d}</option>)}
          </select>
        </Field>
      </div>

      {form.role === 'Student' && (
        <div className="mt-4 flex items-center gap-2.5 px-3.5 py-2.5 bg-sc-orange-lt border border-[#f5d5b2] rounded-lg text-[13px] text-sc-orange-dk">
          <span>⚠</span>
          <span>Face data not enrolled. You can enroll face data after the account is created.</span>
        </div>
      )}
    </Modal>
  )
}

function Field({ label, required, hint, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="text-[12px] font-medium text-text2">
        {label}{required && <span className="text-sc-red"> *</span>}
      </label>
      <div className="[&_input]:w-full [&_select]:w-full [&_input]:bg-surface2 [&_select]:bg-surface2 [&_input]:border [&_select]:border [&_input]:border-border [&_select]:border-border [&_input]:rounded-lg [&_select]:rounded-lg [&_input]:px-3 [&_select]:px-3 [&_input]:py-2 [&_select]:py-2 [&_input]:text-[13.5px] [&_select]:text-[13.5px] [&_input]:text-text1 [&_select]:text-text2 [&_input]:outline-none [&_select]:outline-none [&_input:focus]:border-accent [&_select:focus]:border-accent">
        {children}
      </div>
      {hint && <span className="text-[11px] text-text3">{hint}</span>}
    </div>
  )
}
