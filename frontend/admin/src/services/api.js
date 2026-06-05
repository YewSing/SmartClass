import { apiCall, apiUpload, setToken, clearToken, setRefreshToken, clearRefreshToken } from './client'

// ─── Shape adapter: backend user → frontend user shape ───────────────────────

export function adaptUser(u) {
  return {
    id: u.id,                                    // numeric backend ID
    name: u.name,
    email: u.email,
    role: u.role.charAt(0).toUpperCase() + u.role.slice(1),  // "student" → "Student"
    status: u.status === 'active' ? 'Active' : 'Inactive',
    phone: u.phone ?? '—',
    face: u.face_enrolled ?? false,
    faceDate: u.face_enrolled_at ? u.face_enrolled_at.slice(0, 10) : null,
    faceSamples: u.face_enrolled ? 5 : 0,
    matric: u.student?.matric_no ?? null,
    staffId: u.lecturer?.staff_id ?? null,
    dept: u.lecturer?.dept ?? u.student?.faculty ?? '—',
    programme: u.student?.programme ?? null,
    faculty: u.student?.faculty ?? null,
    yearSem: u.student?.year_sem ?? null,
    color: '#0E6FBF',
    occurrences: (u.enrolled_classes ?? []).map(o => ({
      id: o.id,
      course_code: o.course_code,
      course_name: o.course_name,
      type: o.type,
      label: o.label ?? null,
      day_of_week: o.day_of_week,
      start_time: o.start_time,
      end_time: o.end_time,
    })),
    // keep classes for backward compat with enrollment matrix
    classes: (u.enrolled_classes ?? []).map(o => ({ id: o.id, code: o.course_code, name: o.course_name })),
  }
}

// ─── Auth ─────────────────────────────────────────────────────────────────────

export const login = async (email, password) => {
  const data = await apiCall('POST', '/auth/login', { email, password })
  setToken(data.access_token)
  setRefreshToken(data.refresh_token)
  return adaptUser({ ...data.user, face_enrolled: false })
}

export const logout = () => { clearToken(); clearRefreshToken() }

// ─── Users ────────────────────────────────────────────────────────────────────

export const getUsers = async (role, page = 1) => {
  const qs = new URLSearchParams({ page, limit: 50 })
  if (role) qs.set('role', role)
  const data = await apiCall('GET', `/admin/users?${qs}`)
  return { ...data, items: data.items.map(adaptUser) }
}

export const createUser = async (body) => {
  const u = await apiCall('POST', '/admin/users', body)
  return adaptUser(u)
}

export const updateUser = async (id, body) => {
  const u = await apiCall('PUT', `/admin/users/${id}`, body)
  return adaptUser(u)
}

export const deactivateUser = async (id) => {
  await apiCall('DELETE', `/admin/users/${id}`)
}

// ─── Classes (occurrences) ────────────────────────────────────────────────────

export const getAllClasses = async () => {
  const list = await apiCall('GET', '/classes')
  return list.map(o => ({
    id: o.id,
    code: o.course_code,
    name: o.course_name,
    type: o.type,
    label: o.label ?? null,
    day_of_week: o.day_of_week,
    start_time: o.start_time,
    end_time: o.end_time,
  }))
}

export const enrollStudentInClass = async (studentUserId, occurrenceId) => {
  await apiCall('POST', `/admin/students/${studentUserId}/occurrences/${occurrenceId}`)
}

export const removeStudentFromClass = async (studentUserId, occurrenceId) => {
  await apiCall('DELETE', `/admin/students/${studentUserId}/occurrences/${occurrenceId}`)
}

// ─── Courses ──────────────────────────────────────────────────────────────────

export const getCourses = async () =>
  apiCall('GET', '/admin/courses')

export const getCourseOccurrences = async (courseId) =>
  apiCall('GET', `/admin/courses/${courseId}/occurrences`)

export const getOccurrenceStudents = async (occurrenceId) =>
  apiCall('GET', `/admin/occurrences/${occurrenceId}/students`)

export const enrollInOccurrence = async (occurrenceId, studentUserId) => {
  await apiCall('POST', `/admin/occurrences/${occurrenceId}/students/${studentUserId}`)
}

export const unenrollFromOccurrence = async (occurrenceId, studentUserId) => {
  await apiCall('DELETE', `/admin/occurrences/${occurrenceId}/students/${studentUserId}`)
}

// ─── Face ─────────────────────────────────────────────────────────────────────

export const enrollFace = async (studentUserId, blobs) => {
  const fd = new FormData()
  blobs.forEach(b => fd.append('images', b, 'capture.jpg'))
  return apiUpload('POST', `/admin/students/${studentUserId}/face-enroll`, fd)
}

export const removeFace = async (studentUserId) => {
  await apiCall('DELETE', `/admin/students/${studentUserId}/face-data`)
}

// ─── Face Review Queue ────────────────────────────────────────────────────────

export function adaptReviewEntry(e) {
  const d = new Date(e.flagged_at)
  const ts = d.toLocaleDateString('en-MY', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' })
    + ' ' + d.toLocaleTimeString('en-MY', { hour: '2-digit', minute: '2-digit', timeZone: 'Asia/Kuala_Lumpur' })
  const sessionDate = e.session_date
    ? new Date(e.session_date).toLocaleDateString('en-MY', { day: '2-digit', month: 'short', year: 'numeric', timeZone: 'Asia/Kuala_Lumpur' })
    : null
  return {
    id: e.id,
    ts,
    camera: e.camera_device_id ?? '—',
    session: e.session_id ? `#${e.session_id}` : '—',
    confidence: e.similarity,
    occurrences: e.occurrences,
    closestMatchId: e.closest_match_student_id ?? null,
    closestMatchName: e.closest_match_name ?? null,
    closestMatchConfidence: e.closest_match_confidence ?? null,
    className: e.class_name ?? null,
    sessionDate,
  }
}

export const getReviewQueue = async () => {
  const data = await apiCall('GET', '/admin/face-review')
  return data.map(adaptReviewEntry)
}

export const dismissReviewEntry = (id) =>
  apiCall('DELETE', `/admin/face-review/${id}`)

export const promoteReviewEntry = (id, studentUserId, markPresent = false) =>
  apiCall('POST', `/admin/face-review/${id}/promote`, { student_user_id: studentUserId, mark_present: markPresent })

// ─── Audit log ────────────────────────────────────────────────────────────────

export const getAuditLog = (page = 1, limit = 50) =>
  apiCall('GET', `/admin/audit-logs?page=${page}&limit=${limit}`)
