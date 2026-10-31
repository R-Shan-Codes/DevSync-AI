import { useEffect, useState } from 'react'
import { AlertTriangle, CheckCircle2, CircleDot, RefreshCw, Workflow } from 'lucide-react'
import { request } from './api'

type PipelineTask = {
  task_id: string
  title: string
  status: string
  stage: string
  assignee_id: string | null
  assignment_suggestions: {
    user_id: string
    display_name: string
    role: string
    role_match: boolean
    active_task_count: number
    reason: string
  }[]
  prerequisites: { task_id: string; title: string; status: string }[]
  open_bug_count: number
  latest_review: { decision: string; summary: string } | null
  latest_test_run: { result: string; passed: number; failed: number; total: number } | null
  gates: string[]
  ready_for_next_step: boolean
  next_action: string
}
type Pipeline = { total_tasks: number; stage_counts: Record<string, number>; tasks: PipelineTask[] }

const label = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, c => c.toUpperCase())

export default function PipelineCenter({ token, projectId }: { token: string; projectId: string }) {
  const [pipeline, setPipeline] = useState<Pipeline | null>(null)
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  async function refresh() {
    if (!projectId) return
    setBusy(true)
    setError('')
    try {
      setPipeline(await request<Pipeline>(`/projects/${projectId}/pipeline`, token))
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load development pipeline')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => { setPipeline(null); refresh() }, [token, projectId])

  if (!projectId) return <section className="panel muted">Select a project to view its development pipeline.</section>
  if (error) return <section className="panel"><div className="error">{error}</div><button className="primary" onClick={refresh}>Retry</button></section>
  if (!pipeline) return <section className="panel muted">Loading development pipeline…</section>

  return <div className="pipeline-center">
    <section className="panel">
      <div className="panel-heading"><div><h3>Smart development pipeline</h3><p className="muted">Task → coding → review → testing → merge. Readiness is calculated from recorded evidence; DevSync does not advance tasks automatically.</p></div><button className="icon-button" onClick={refresh} disabled={busy}><RefreshCw size={16}/>{busy ? 'Refreshing…' : 'Refresh'}</button></div>
      <div className="stats-grid">{Object.entries(pipeline.stage_counts).map(([stage, count]) => <div className="stat-card" key={stage}><span>{label(stage)}</span><strong>{count}</strong></div>)}</div>
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h3>Workflow tasks</h3><p className="muted">{pipeline.total_tasks} tasks with dependency, review, test and bug evidence.</p></div><Workflow size={18}/></div>
      {pipeline.tasks.length ? pipeline.tasks.map(task => <article className="pipeline-task" key={task.task_id}>
        <div className="panel-heading"><div><b>{task.title}</b><small className="muted">{label(task.stage)} · {label(task.status)}</small></div><span className={task.ready_for_next_step ? 'pill' : 'role'}>{task.ready_for_next_step ? <><CheckCircle2 size={13}/> Ready</> : <><AlertTriangle size={13}/> Blocked</>}</span></div>
        <p className="muted">Next: {task.next_action}</p>
        {task.gates.length > 0 && <div className="pipeline-gates">{task.gates.map(gate => <span className="role" key={gate}>{label(gate)}</span>)}</div>}
        {task.assignment_suggestions.length > 0 && <div className="pipeline-assignment"><b>Suggested owners (not assigned)</b>{task.assignment_suggestions.map(candidate => <small key={candidate.user_id}>{candidate.display_name} · {label(candidate.role)} · {candidate.active_task_count} active task(s)</small>)}</div>}
        {task.prerequisites.length > 0 && <small>Waiting for: {task.prerequisites.map(item => `${item.title} (${label(item.status)})`).join(', ')}</small>}
        {task.latest_review && <small>Latest review: {label(task.latest_review.decision)}{task.latest_review.summary ? ` — ${task.latest_review.summary}` : ''}</small>}
        {task.latest_test_run && <small>Latest tests: {task.latest_test_run.passed}/{task.latest_test_run.total} passed · {task.latest_test_run.failed} failed</small>}
        {task.latest_ai_review && <div className="pipeline-ai-evidence"><b>AI review evidence · advisory</b><small>{label(task.latest_ai_review.artifact_type)} · {task.latest_ai_review.source_key} · {task.latest_ai_review.finding_count} finding(s)</small><small>{task.latest_ai_review.summary}</small></div>}
        {task.open_bug_count > 0 && <small><CircleDot size={12}/> {task.open_bug_count} open bug(s)</small>}
      </article>) : <p className="muted">No tasks in this project yet.</p>}
    </section>
  </div>
}
