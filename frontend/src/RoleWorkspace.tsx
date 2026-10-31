import { useEffect, useState } from 'react'
import { Activity, ClipboardCheck, Code2, ShieldCheck, Users } from 'lucide-react'
import { Member, Task, request } from './api'
import BugReports from './BugReports'
import TaskWorkflow from './TaskWorkflow'

type TestRun = { id:string; task_id:string; tester_id:string; result:string; summary:string; total:number; passed:number; failed:number; created_at:string }
type Props = { token:string; projectId:string; member:Member|null; tasks:Task[]; members:Member[]; onRefresh:()=>void }
const label=(value:string)=>value.replaceAll('_',' ').replace(/\\b\\w/g,c=>c.toUpperCase())

export default function RoleWorkspace({token,projectId,member,tasks,members,onRefresh}:Props){
 const [runs,setRuns]=useState<TestRun[]>([])
 const [taskId,setTaskId]=useState('')
 const [result,setResult]=useState('passed')
 const [summary,setSummary]=useState('')
 const [total,setTotal]=useState(1)
 const [passed,setPassed]=useState(1)
 const [failed,setFailed]=useState(0)
 const [assignees,setAssignees]=useState<Record<string,string>>({})
 const [message,setMessage]=useState('')
 const [busy,setBusy]=useState(false)
 const role=member?.role||'frontend_developer'
 const admin=Boolean(member?.permissions.manage_team)
 const tester=role==='tester_qa_engineer'
 const mine=tasks.filter(t=>t.assignee_id===member?.user_id)
 useEffect(()=>{if(!projectId)return;request<TestRun[]>(`/projects/${projectId}/test-runs`,token).then(setRuns).catch(()=>setRuns([]))},[projectId,token])
 async function assign(task:Task){
  const assignee_id=assignees[task.id]
  if(!assignee_id)return
  setBusy(true);setMessage('')
  try{await request<Task>(`/projects/${projectId}/tasks/${task.id}`,token,{method:'PATCH',body:JSON.stringify({assignee_id})});setMessage('Task assignment saved.');onRefresh()}
  catch(e){setMessage(e instanceof Error?e.message:'Could not assign task')}
  finally{setBusy(false)}
 }
 async function submitRun(){
  if(!taskId){setMessage('Select a task to test.');return}
  setBusy(true);setMessage('')
  try{
   await request<TestRun>(`/projects/${projectId}/test-runs`,token,{method:'POST',body:JSON.stringify({task_id:taskId,result,summary,total,passed,failed})})
   const latest=await request<TestRun[]>(`/projects/${projectId}/test-runs`,token);setRuns(latest);setSummary('');setMessage('Test result recorded in the project timeline.');onRefresh()
  }catch(e){setMessage(e instanceof Error?e.message:'Could not save test result')}
  finally{setBusy(false)}
 }
 const title=admin?'Admin control room':tester?'QA testing workspace':role==='frontend_developer'?'Frontend development workspace':role==='backend_developer'?'Backend development workspace':`${label(role)} workspace`
 return <div className="role-workspace">
  <section className="welcome-row"><div><span className="eyebrow">YOUR ROLE WORKSPACE</span><h1>{title}</h1><p className="muted">Signed in as {member?.display_name||'project member'} · {label(role)}</p></div><span className="pill"><Activity size={14}/> Connected to project</span></section>
  {message&&<div className="github-message">{message}</div>}
  <div className="stats-grid">
   <div className="stat-card"><Code2 size={18}/><span>Project tasks</span><strong>{tasks.length}</strong></div>
   <div className="stat-card"><ClipboardCheck size={18}/><span>Assigned to me</span><strong>{mine.length}</strong></div>
   <div className="stat-card"><ShieldCheck size={18}/><span>Test runs</span><strong>{runs.length}</strong></div>
   <div className="stat-card"><Users size={18}/><span>Team members</span><strong>{members.length}</strong></div>
  </div>
  {admin&&<section className="panel"><div className="panel-heading"><div><h3>Task assignment control</h3><p className="muted">Assign project tasks to registered team members.</p></div><Users size={18}/></div>
   {tasks.length?tasks.map(t=><div className="role-task-row" key={t.id}><div><b>{t.title}</b><small>{label(t.status)}</small></div><select value={assignees[t.id]??t.assignee_id??''} onChange={e=>setAssignees(v=>({...v,[t.id]:e.target.value}))}><option value="">Unassigned</option>{members.map(m=><option key={m.user_id} value={m.user_id}>{m.display_name} · {label(m.role)}</option>)}</select><button className="primary" disabled={busy||!(assignees[t.id]??t.assignee_id)} onClick={()=>assign(t)}>Assign</button></div>):<p className="muted">Create tasks in the Tasks tab first.</p>}
  </section>}
  <section className="panel"><div className="panel-heading"><div><h3>{tester?'Tasks ready for QA':admin?'Project delivery board':'My assigned work'}</h3><p className="muted">{tester?'Review submitted work and record test outcomes.':admin?'Monitor task ownership and delivery status.':'Work assigned to your account.'}</p></div><Code2 size={18}/></div>
   {(admin?tasks:tester?tasks.filter(t=>['ready_for_testing','testing','failed'].includes(t.status)||t.assignee_id===member?.user_id):mine).map(t=><div className="role-task-row" key={t.id}><div><b>{t.title}</b><small>{label(t.status)} · {members.find(m=>m.user_id===t.assignee_id)?.display_name||'Unassigned'}</small></div><span className="role">{label(t.status)}</span></div>)}
   {!(admin?tasks:tester?tasks.filter(t=>['ready_for_testing','testing','failed'].includes(t.status)||t.assignee_id===member?.user_id):mine).length&&<p className="muted">No tasks are currently assigned to this workspace.</p>}
  </section>
  {tester&&<section className="panel"><div className="panel-heading"><div><h3>Record a test run</h3><p className="muted">Save pass, fail or blocked results against a project task.</p></div><ClipboardCheck size={18}/></div>
   <div className="test-run-form"><label>Task<select value={taskId} onChange={e=>setTaskId(e.target.value)}><option value="">Select task</option>{tasks.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
    <label>Result<select value={result} onChange={e=>setResult(e.target.value)}><option value="passed">Passed</option><option value="failed">Failed</option><option value="blocked">Blocked</option></select></label>
    <label>Total tests<input type="number" min="0" value={total} onChange={e=>setTotal(Number(e.target.value))}/></label>
    <label>Passed<input type="number" min="0" value={passed} onChange={e=>setPassed(Number(e.target.value))}/></label>
    <label>Failed<input type="number" min="0" value={failed} onChange={e=>setFailed(Number(e.target.value))}/></label>
    <label className="test-summary">Summary<textarea value={summary} onChange={e=>setSummary(e.target.value)} placeholder="What was tested? Include observed behavior or bug details."/></label>
   </div><button className="primary" disabled={busy||!taskId||passed+failed>total||(result==='failed'&&failed===0)||(result==='passed'&&failed>0)} onClick={submitRun}>{busy?'Saving…':'Save test result'}</button>
  </section>}
  <TaskWorkflow token={token} projectId={projectId} member={member} tasks={admin?tasks:tester?tasks.filter(t=>['ready_for_testing','testing','failed','passed'].includes(t.status)||t.assignee_id===member?.user_id):mine} onRefresh={onRefresh}/>
  <BugReports token={token} projectId={projectId} member={member} tasks={tasks}/>
  <section className="panel"><div className="panel-heading"><div><h3>Recent QA results</h3><p className="muted">Persisted test execution history for this project.</p></div><ClipboardCheck size={18}/></div>
   {runs.length?runs.map(run=><div className="role-task-row" key={run.id}><div><b>{label(run.result)} · {tasks.find(t=>t.id===run.task_id)?.title||'Project task'}</b><small>{run.passed} passed · {run.failed} failed · {run.total} total · {new Date(run.created_at).toLocaleString()}</small><small>{run.summary}</small></div><span className="role">{label(run.result)}</span></div>):<p className="muted">No test runs recorded yet.</p>}
  </section>
 </div>
}
