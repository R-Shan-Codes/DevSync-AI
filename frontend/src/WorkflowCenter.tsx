import { useEffect, useMemo, useState } from 'react'
import { Bug, CheckCircle2, ClipboardCheck, MessageSquareText, RefreshCw, ShieldCheck, Users } from 'lucide-react'
import { Member, Task, request } from './api'

type Review = { id: string; task_id: string; reviewer_id: string; decision: string; summary: string; findings: string; created_at: string }
type TestRun = { id: string; task_id: string; tester_id: string; result: string; summary: string; total: number; passed: number; failed: number; created_at: string }
type BugReport = { id: string; task_id: string; title: string; description: string; severity: string; status: string; resolution: string | null; created_at: string; updated_at: string }

type Props = { token: string; projectId: string; member: Member | null; tasks: Task[]; members: Member[]; onRefresh: () => void }
const pretty = (value: string) => value.replaceAll('_', ' ').replace(/\b\w/g, char => char.toUpperCase())

export default function WorkflowCenter({ token, projectId, member, tasks, members, onRefresh }: Props) {
  const [selectedTaskId, setSelectedTaskId] = useState('')
  const [reviews, setReviews] = useState<Review[]>([])
  const [testRuns, setTestRuns] = useState<TestRun[]>([])
  const [bugs, setBugs] = useState<BugReport[]>([])
  const [assigneeId, setAssigneeId] = useState('')
  const [decision, setDecision] = useState('approved')
  const [reviewSummary, setReviewSummary] = useState('')
  const [findings, setFindings] = useState('')
  const [testResult, setTestResult] = useState('passed')
  const [testSummary, setTestSummary] = useState('')
  const [total, setTotal] = useState(1)
  const [passed, setPassed] = useState(1)
  const [failed, setFailed] = useState(0)
  const [bugTitle, setBugTitle] = useState('')
  const [bugDescription, setBugDescription] = useState('')
  const [bugSeverity, setBugSeverity] = useState('medium')
  const [message, setMessage] = useState('')
  const [error, setError] = useState('')
  const [loading, setLoading] = useState(false)
  const [saving, setSaving] = useState(false)

  const selectedTask = tasks.find(task => task.id === selectedTaskId) || tasks[0]
  const canReview = Boolean(member?.permissions.review)
  const canEdit = Boolean(member?.permissions.edit)
  const canAssign = Boolean(member?.permissions.manage_team)
  const taskReviews = useMemo(() => reviews.filter(item => item.task_id === selectedTask?.id), [reviews, selectedTask?.id])
  const taskRuns = useMemo(() => testRuns.filter(item => item.task_id === selectedTask?.id), [testRuns, selectedTask?.id])
  const taskBugs = useMemo(() => bugs.filter(item => item.task_id === selectedTask?.id), [bugs, selectedTask?.id])

  async function loadEvidence() {
    if (!projectId) return
    setLoading(true)
    setError('')
    try {
      const [reviewRows, runRows, bugRows] = await Promise.all([
        request<Review[]>(`/projects/${projectId}/reviews`, token),
        request<TestRun[]>(`/projects/${projectId}/test-runs`, token),
        request<BugReport[]>(`/projects/${projectId}/bugs`, token),
      ])
      setReviews(reviewRows)
      setTestRuns(runRows)
      setBugs(bugRows)
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load workflow evidence')
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => { setSelectedTaskId(''); setReviews([]); setTestRuns([]); setBugs([]); loadEvidence() }, [projectId, token])
  useEffect(() => { setAssigneeId(selectedTask?.assignee_id || '') }, [selectedTask?.id, selectedTask?.assignee_id])

  async function perform(action: () => Promise<unknown>, success: string) {
    setSaving(true); setError(''); setMessage('')
    try {
      await action()
      setMessage(success)
      await loadEvidence()
      onRefresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Workflow action failed')
    } finally {
      setSaving(false)
    }
  }

  if (!projectId) return <section className="panel muted">Select a project to coordinate its delivery workflow.</section>

  return <div className="workflow-center">
    <section className="panel">
      <div className="panel-heading">
        <div><h3>Collaborative delivery workspace</h3><p className="muted">Coordinate task ownership, code review, QA evidence and bug resolution in one place.</p></div>
        <button className="icon-button" onClick={loadEvidence} disabled={loading}><RefreshCw size={15}/>{loading ? 'Loading…' : 'Refresh evidence'}</button>
      </div>
      {message && <div className="github-message">{message}</div>}
      {error && <div className="error">{error}</div>}
      {!tasks.length ? <p className="muted">Create a task before recording reviews, tests or bugs.</p> : <>
        <label className="workflow-task-picker">Selected task
          <select value={selectedTask?.id || ''} onChange={event => setSelectedTaskId(event.target.value)}>
            {tasks.map(task => <option key={task.id} value={task.id}>{task.title} · {pretty(task.status)}</option>)}
          </select>
        </label>
        {selectedTask && <div className="workflow-task-summary">
          <div><b>{selectedTask.title}</b><small>{pretty(selectedTask.status)} · {members.find(item => item.user_id === selectedTask.assignee_id)?.display_name || 'Unassigned'}</small></div>
          <span className="role">{pretty(selectedTask.status)}</span>
        </div>}
      </>}
    </section>

    {selectedTask && <section className="workflow-action-grid">
      <article className="panel">
        <div className="panel-heading"><div><h3>Task ownership</h3><p className="muted">Assign responsibility to a project teammate.</p></div><Users size={18}/></div>
        <label className="workflow-field">Assignee
          <select value={assigneeId} disabled={!canAssign} onChange={event => setAssigneeId(event.target.value)}>
            <option value="">Unassigned</option>
            {members.map(item => <option key={item.user_id} value={item.user_id}>{item.display_name} · {pretty(item.role)}</option>)}
          </select>
        </label>
        {canAssign ? <button className="primary" disabled={saving || assigneeId === (selectedTask.assignee_id || '')} onClick={() => perform(() => request(`/projects/${projectId}/tasks/${selectedTask.id}`, token, { method: 'PATCH', body: JSON.stringify({ assignee_id: assigneeId || null }) }), 'Task ownership updated.')}>Save assignment</button> : <small className="muted">Team-management permission is required to change task ownership.</small>}
      </article>

      <article className="panel">
        <div className="panel-heading"><div><h3>Code review</h3><p className="muted">Record an explicit reviewer decision and findings.</p></div><MessageSquareText size={18}/></div>
        {canReview ? <>
          <label className="workflow-field">Decision<select value={decision} onChange={event => setDecision(event.target.value)}><option value="approved">Approved</option><option value="changes_requested">Changes requested</option><option value="commented">Comment only</option></select></label>
          <label className="workflow-field">Summary<input value={reviewSummary} onChange={event => setReviewSummary(event.target.value)} maxLength={5000} placeholder="Review summary"/></label>
          <label className="workflow-field">Findings<textarea value={findings} onChange={event => setFindings(event.target.value)} maxLength={20000} placeholder="Issues, suggestions or approval rationale"/></label>
          <button className="primary" disabled={saving} onClick={() => perform(() => request(`/projects/${projectId}/reviews`, token, { method: 'POST', body: JSON.stringify({ task_id: selectedTask.id, decision, summary: reviewSummary, findings }) }), 'Code review recorded.')}>Submit review</button>
        </> : <small className="muted">Review permission is required to submit a code review.</small>}
      </article>

      <article className="panel">
        <div className="panel-heading"><div><h3>QA test evidence</h3><p className="muted">Attach a test outcome to this task.</p></div><ClipboardCheck size={18}/></div>
        {canEdit ? <>
          <label className="workflow-field">Result<select value={testResult} onChange={event => setTestResult(event.target.value)}><option value="passed">Passed</option><option value="failed">Failed</option><option value="blocked">Blocked</option></select></label>
          <div className="workflow-number-grid">
            <label className="workflow-field">Total<input type="number" min="0" value={total} onChange={event => setTotal(Number(event.target.value))}/></label>
            <label className="workflow-field">Passed<input type="number" min="0" value={passed} onChange={event => setPassed(Number(event.target.value))}/></label>
            <label className="workflow-field">Failed<input type="number" min="0" value={failed} onChange={event => setFailed(Number(event.target.value))}/></label>
          </div>
          <label className="workflow-field">Execution notes<textarea value={testSummary} onChange={event => setTestSummary(event.target.value)} maxLength={10000} placeholder="Test scope, environment and observed result"/></label>
          <button className="primary" disabled={saving || passed + failed > total || (testResult === 'failed' && failed === 0) || (testResult === 'passed' && failed > 0)} onClick={() => perform(() => request(`/projects/${projectId}/test-runs`, token, { method: 'POST', body: JSON.stringify({ task_id: selectedTask.id, result: testResult, summary: testSummary, total, passed, failed }) }), 'QA test result recorded.')}>Record test result</button>
        </> : <small className="muted">Edit permission is required to record a test run.</small>}
      </article>

      <article className="panel">
        <div className="panel-heading"><div><h3>Bug reporting</h3><p className="muted">Create a trackable issue linked to this task.</p></div><Bug size={18}/></div>
        {canEdit ? <>
          <label className="workflow-field">Bug title<input value={bugTitle} onChange={event => setBugTitle(event.target.value)} minLength={3} maxLength={180} placeholder="Short, actionable title"/></label>
          <label className="workflow-field">Severity<select value={bugSeverity} onChange={event => setBugSeverity(event.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
          <label className="workflow-field">Description<textarea value={bugDescription} onChange={event => setBugDescription(event.target.value)} minLength={5} maxLength={12000} placeholder="Steps to reproduce, expected and actual behavior"/></label>
          <button className="primary" disabled={saving || bugTitle.trim().length < 3 || bugDescription.trim().length < 5} onClick={() => perform(async () => {
            await request(`/projects/${projectId}/bugs`, token, { method: 'POST', body: JSON.stringify({ task_id: selectedTask.id, title: bugTitle.trim(), description: bugDescription.trim(), severity: bugSeverity }) })
            setBugTitle(''); setBugDescription('')
          }, 'Bug report created and linked to the task.')}>Create bug report</button>
        </> : <small className="muted">Edit permission is required to report a bug.</small>}
      </article>
    </section>}

    {selectedTask && <section className="panel">
      <div className="panel-heading"><div><h3>Task evidence and history</h3><p className="muted">Persisted review decisions, QA runs and open issues for the selected task.</p></div><ShieldCheck size={18}/></div>
      <div className="workflow-evidence-grid">
        <div><h4>Code reviews · {taskReviews.length}</h4>{taskReviews.length ? taskReviews.map(item => <div className="workflow-evidence" key={item.id}><b>{pretty(item.decision)}</b><small>{item.summary || 'No summary'} · {new Date(item.created_at).toLocaleString()}</small>{item.findings && <p>{item.findings}</p>}</div>) : <p className="muted">No reviews recorded.</p>}</div>
        <div><h4>Test runs · {taskRuns.length}</h4>{taskRuns.length ? taskRuns.map(item => <div className="workflow-evidence" key={item.id}><b>{pretty(item.result)} · {item.passed}/{item.total} passed</b><small>{item.failed} failed · {new Date(item.created_at).toLocaleString()}</small>{item.summary && <p>{item.summary}</p>}</div>) : <p className="muted">No test runs recorded.</p>}</div>
        <div><h4>Bug reports · {taskBugs.length}</h4>{taskBugs.length ? taskBugs.map(item => <div className="workflow-evidence" key={item.id}><b>{item.title}</b><small>{pretty(item.severity)} severity · {pretty(item.status)}</small><p>{item.description}</p></div>) : <p className="muted">No bug reports recorded.</p>}</div>
      </div>
      <p className="muted workflow-note"><CheckCircle2 size={13}/> Recording evidence does not automatically approve, advance, close or merge a task. Existing role permissions and explicit workflow transitions remain in force.</p>
    </section>}
  </div>
}
