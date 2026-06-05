import { useEffect, useState } from 'react'
import { useAdmin } from '../context/AdminContext'
import Pagination from '../components/ui/Pagination'

export default function ClassManagementView() {
  const { state, loadAllCourses, openModal } = useAdmin()
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)
  const [pageSize, setPageSize] = useState(10)

  useEffect(() => { loadAllCourses() }, [])
  useEffect(() => { setPage(1) }, [search, pageSize])

  const filtered = (state.allCourses ?? []).filter(c =>
    c.code.toLowerCase().includes(search.toLowerCase()) ||
    c.name.toLowerCase().includes(search.toLowerCase())
  )

  const paginated = filtered.slice((page - 1) * pageSize, page * pageSize)

  return (
    <div className="bg-surface border border-border rounded-xl overflow-hidden">
      <div className="flex items-center gap-3 px-5 py-4 border-b border-border">
        <span className="text-[14px] font-semibold text-text1">Class Management</span>
        <span className="text-[12px] text-text3 ml-1">{filtered.length} courses</span>
        <div className="flex items-center gap-2 bg-surface2 border border-border rounded-lg px-3 py-1.5 ml-auto">
          <span className="text-text3 text-[13px]">⌕</span>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Search courses…"
            className="bg-transparent outline-none text-[13px] text-text1 w-48 placeholder:text-text3"
          />
        </div>
      </div>

      <table className="w-full border-collapse">
        <thead>
          <tr className="bg-surface2">
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Code</th>
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-left border-b border-border">Course Name</th>
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-center border-b border-border">Occurrences</th>
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 text-center border-b border-border">Total Students</th>
            <th className="text-[11px] font-semibold uppercase tracking-[0.07em] text-text3 px-5 py-2.5 border-b border-border"></th>
          </tr>
        </thead>
        <tbody>
          {paginated.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-5 py-10 text-center text-[13px] text-text3">
                {(state.allCourses ?? []).length === 0 ? 'Loading…' : 'No courses match your search.'}
              </td>
            </tr>
          ) : (
            paginated.map(c => (
              <tr key={c.id} className="hover:bg-surface2 transition-colors">
                <td className="px-5 py-3 border-b border-border">
                  <span className="font-semibold text-accent text-[13px]">{c.code}</span>
                </td>
                <td className="px-5 py-3 border-b border-border text-[13px] text-text1">{c.name}</td>
                <td className="px-5 py-3 border-b border-border text-center text-[13px] text-text2">{c.occurrence_count}</td>
                <td className="px-5 py-3 border-b border-border text-center text-[13px] text-text2">{c.enrolled_count}</td>
                <td className="px-5 py-3 border-b border-border text-right">
                  <button
                    onClick={() => openModal('courseDetail', { courseId: c.id, courseCode: c.code, courseName: c.name })}
                    className="text-[13px] text-text2 hover:text-text1 border border-border rounded-md px-2.5 py-1 bg-transparent hover:bg-surface2 transition-all"
                  >
                    View
                  </button>
                </td>
              </tr>
            ))
          )}
        </tbody>
      </table>

      <Pagination
        total={filtered.length}
        page={page}
        pageSize={pageSize}
        onPage={setPage}
        onPageSize={setPageSize}
      />
    </div>
  )
}
