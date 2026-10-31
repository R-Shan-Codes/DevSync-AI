import { useEffect, useState } from 'react'
import { Search, SlidersHorizontal } from 'lucide-react'
import { request, Task } from './api'

type Props = { token: string; projectId: string; refreshKey: Task[]; onStatusChange: (task: Task, status: string) => void }
const stages = ['backlog','in_progress','submitted','in_review','approved','ready_for_testing','testing','failed','passed','ready_for_merge','merged','cancelled']
const priorities = ['low','medium','high','urgent']

export default function TaskSearchBoard({ token, projectId, refreshKey, onStatusChange }: Props) {
  const [query, setQuery] = useState('')
  const [status, setStatus] = useState('')
  const [priority, setPriority] = useState('')
  const [rows, setRows] = useState<Task[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  useEffect(() => {
    if (!projectId) { setRows([]); return }
    let active = true
    const timer = window.setTimeout(async () => {
      setBusy(true); setError('')
      const params = new URLSearchParams()
      if (query.trim()) params.set('q', query.trim())
      if (status) params.set('status', status)
      if (priority) params.set('priority', priority)
      params.set('limit', '200')
      try {
        const result = await request<Task[]>(`/projects/${projectId}/tasks?${params.toString()}`, token)
        if (active) setRows(result)
      } catch (e) { if (active) setError(e instanceof Error ? e.message : 'Task search failed') }
      finally { if (active) setBusy(false) }
    }, 220)
    return () => { active = false; window.clearTimeout(timer) }
  }, [token, projectId, query, status, priority, refreshKey])
  return <div className="task-search-board">
    <div className="task-search-controls">
      <label><Search size={14}/><input value={query} onChange={event => setQuery(event.target.value)} placeholder="Search task titles and descriptions"/></label>
      <label><SlidersHorizontal size={14}/><select value={status} onChange={event => setStatus(event.target.value)}><option value="">All statuses</option>{stages.map(value => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}</select></label>
      <select aria-label="Filter by priority" value={priority} onChange={event => setPriority(event.target.value)}><option value="">All priorities</option>{priorities.map(value => <option key={value} value={value}>{value}</option>)}</select>
    </div>
    <div className="task-search-summary">{busy ? 'Searching…' : rows.length + ' matching task(s)'}</div>
    {error && <div className="error">{error}</div>}
    <div className="task-list">{rows.map(task => <div className="task-row" key={task.id}>
      <div><b>{task.title}</b><small>{task.description || 'No description'} · {task.priority} priority</small></div>
      <select aria-label={'Status for ' + task.title} value={task.status} onChange={event => onStatusChange(task, event.target.value)}>
        {stages.map(value => <option key={value} value={value}>{value.replaceAll('_',' ')}</option>)}
      </select>
    </div>)}</div>
    {!busy && !rows.length && !error && <p className="muted">No tasks match these filters.</p>}
  </div>
}
