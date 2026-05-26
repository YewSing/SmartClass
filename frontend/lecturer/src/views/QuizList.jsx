import { useState } from 'react'
import { useLecturer } from '../context/LecturerContext'
import StatusBar from '../components/layout/StatusBar'
import Topbar from '../components/layout/Topbar'
import { QUIZZES } from '../data/mockData'

export default function QuizList() {
  const { navigate, openModal } = useLecturer()
  const [filter, setFilter] = useState('all')

  const visible = filter === 'all' ? QUIZZES : QUIZZES.filter(q => q.status === filter)

  return (
    <>
      <StatusBar time="10:14" />
      <Topbar
        title="Quiz & Poll"
        sub="WIA2005 — Session in progress"
        right={<button className="btn btn-primary btn-sm" onClick={() => navigate('create-quiz')}><i className="fa fa-plus"></i> Create</button>}
      />
      <div className="quiz-filter-row" style={{ flexShrink: 0 }}>
        {['all', 'active', 'closed', 'draft'].map(f => (
          <button key={f} className={`filter-pill${filter === f ? ' active' : ''}`} onClick={() => setFilter(f)}>
            {f.charAt(0).toUpperCase() + f.slice(1)}
          </button>
        ))}
      </div>
      <div className="scroll-body">
        <div style={{ padding: '10px 16px 4px', fontSize: 12, color: 'var(--text-sub)' }}>{visible.length} questions this session</div>
        {visible.map(q => (
          <div key={q.id} className="quiz-card-item" onClick={() => openModal('quiz', q)}>
            <div className="qci-top">
              <div className="qci-q">{q.question}</div>
              <span className={`badge ${q.status === 'active' ? 'blue' : q.status === 'closed' ? 'gray' : 'yellow'}`}>
                {q.status.charAt(0).toUpperCase() + q.status.slice(1)}
              </span>
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginTop: 6 }}>
              <span style={{ fontSize: 11, color: 'var(--text-hint)' }}>
                <i className="fa fa-clock" style={{ fontSize: 11 }}></i> {q.time}{q.timer ? ` · ${q.timer} timer` : ' · not pushed yet'}
              </span>
              {q.status === 'active'  && <span style={{ fontSize: 11, color: 'var(--text-hint)' }}>· {q.answered}/{q.total} answered</span>}
              {q.status === 'closed'  && <span style={{ fontSize: 11, color: 'var(--green-dk)', fontWeight: 700 }}>· {q.pct}% correct</span>}
            </div>
            {q.status === 'active' && (
              <div style={{ display: 'flex', alignItems: 'center', gap: 6, marginTop: 8 }}>
                <div style={{ flex: 1, height: 4, background: 'var(--gray-100)', borderRadius: 2, overflow: 'hidden' }}>
                  <div style={{ width: `${q.pct}%`, height: '100%', background: 'var(--blue)', borderRadius: 2 }}></div>
                </div>
                <span style={{ fontSize: 10, color: 'var(--text-hint)' }}>{q.pct}%</span>
              </div>
            )}
            {q.status === 'closed' && (
              <div style={{ display: 'flex', gap: 10, marginTop: 8 }}>
                <span style={{ fontSize: 11, background: 'var(--green-lt)', color: 'var(--green-dk)', padding: '2px 7px', borderRadius: 10, fontWeight: 700 }}>{q.correct_count} Correct</span>
                <span style={{ fontSize: 11, background: 'var(--red-lt)', color: 'var(--red-dk)', padding: '2px 7px', borderRadius: 10, fontWeight: 700 }}>{q.wrong_count} Wrong</span>
                <span style={{ fontSize: 11, background: 'var(--gray-100)', color: 'var(--gray-500)', padding: '2px 7px', borderRadius: 10, fontWeight: 700 }}>{q.unanswered_count} Skipped</span>
              </div>
            )}
            {q.status === 'draft' && (
              <div style={{ marginTop: 8 }}>
                <button className="btn btn-primary btn-sm" onClick={e => { e.stopPropagation(); openModal('quiz', q) }}>
                  <i className="fa fa-paper-plane"></i> Push now
                </button>
              </div>
            )}
          </div>
        ))}
        <div style={{ height: 20 }}></div>
      </div>
    </>
  )
}
