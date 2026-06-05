export default function Pagination({ total, page, pageSize, onPage, onPageSize }) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize))
  const start = total === 0 ? 0 : (page - 1) * pageSize + 1
  const end = Math.min(page * pageSize, total)

  return (
    <div className="flex items-center gap-4 px-5 py-3 border-t border-border">
      <div className="flex items-center gap-2 text-[12px] text-text3">
        <span>Rows per page</span>
        <select
          value={pageSize}
          onChange={e => { onPageSize(Number(e.target.value)); onPage(1) }}
          className="bg-surface2 border border-border rounded-md px-2 py-0.5 text-[12px] text-text2 outline-none"
        >
          {[10, 25, 50].map(n => <option key={n} value={n}>{n}</option>)}
        </select>
      </div>

      <span className="ml-auto text-[12px] text-text3">
        {total === 0 ? 'No entries' : `${start}–${end} of ${total}`}
      </span>

      <div className="flex gap-1">
        <button
          onClick={() => onPage(page - 1)}
          disabled={page <= 1}
          className="w-7 h-7 flex items-center justify-center rounded-md border border-border text-text2 hover:bg-surface2 disabled:opacity-40 disabled:cursor-not-allowed text-[15px] leading-none"
        >
          ‹
        </button>
        <button
          onClick={() => onPage(page + 1)}
          disabled={page >= totalPages}
          className="w-7 h-7 flex items-center justify-center rounded-md border border-border text-text2 hover:bg-surface2 disabled:opacity-40 disabled:cursor-not-allowed text-[15px] leading-none"
        >
          ›
        </button>
      </div>
    </div>
  )
}
