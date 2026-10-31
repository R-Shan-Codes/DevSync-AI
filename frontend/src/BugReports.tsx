import { useEffect, useState } from 'react'
import { AlertTriangle } from 'lucide-react'
import { Member, Task, request } from './api'
type Bug = {id:string;task_id:string;title:string;description:string;severity:string;status:string;created_at:string}
type Props = {token:string;projectId:string;member:Member|null;tasks:Task[]}
export default function BugReports({token,projectId,member,tasks}:Props){
 const [bugs,setBugs]=useState<Bug[]>([]); const [taskId,setTaskId]=useState(''); const [title,setTitle]=useState(''); const [description,setDescription]=useState(''); const [severity,setSeverity]=useState('medium'); const [message,setMessage]=useState(''); const [busy,setBusy]=useState(false)
 async function load(){try{setBugs(await request<Bug[]>(`/projects/${projectId}/bugs`,token))}catch(e){setMessage(e instanceof Error?e.message:'Could not load bug reports')}}
 useEffect(()=>{if(projectId)load()},[projectId,token])
 async function submit(){setBusy(true);setMessage('');try{await request<Bug>(`/projects/${projectId}/bugs`,token,{method:'POST',body:JSON.stringify({task_id:taskId,title,description,severity})});setTitle('');setDescription('');await load();setMessage('Bug report saved.')}catch(e){setMessage(e instanceof Error?e.message:'Could not save bug report')}finally{setBusy(false)}}
 async function update(bug:Bug,status:string){setBusy(true);try{const saved=await request<Bug>(`/projects/${projectId}/bugs/${bug.id}`,token,{method:'PATCH',body:JSON.stringify({status})});setBugs(old=>old.map(item=>item.id===bug.id?saved:item))}catch(e){setMessage(e instanceof Error?e.message:'Could not update bug')}finally{setBusy(false)}}
 return <section className="panel"><div className="panel-heading"><div><h3>Bug reports</h3><p className="muted">Capture defects against tasks and track their resolution.</p></div><AlertTriangle size={18}/></div>
  {message&&<p className="muted">{message}</p>}<div className="test-run-form">
   <label>Related task<select value={taskId} onChange={e=>setTaskId(e.target.value)}><option value="">Select task</option>{tasks.map(t=><option key={t.id} value={t.id}>{t.title}</option>)}</select></label>
   <label>Severity<select value={severity} onChange={e=>setSeverity(e.target.value)}><option value="low">Low</option><option value="medium">Medium</option><option value="high">High</option><option value="critical">Critical</option></select></label>
   <label className="test-summary">Bug title<input value={title} onChange={e=>setTitle(e.target.value)} maxLength={180} placeholder="Short issue title"/></label>
   <label className="test-summary">Steps and observed behavior<textarea value={description} onChange={e=>setDescription(e.target.value)} maxLength={10000} placeholder="Steps to reproduce, expected result, actual result…"/></label>
  </div><button className="primary" disabled={busy||!taskId||title.trim().length<3||description.trim().length<5} onClick={submit}>{busy?'Saving…':'Submit bug report'}</button>
  {bugs.length?bugs.map(b=><div className="role-task-row" key={b.id}><div><b>{b.title}</b><small>{b.severity.toUpperCase()} · {tasks.find(t=>t.id===b.task_id)?.title||'Project task'} · {new Date(b.created_at).toLocaleString()}</small><small>{b.description}</small></div>{member?.permissions.review?<select value={b.status} disabled={busy} onChange={e=>update(b,e.target.value)}><option value="open">Open</option><option value="triaged">Triaged</option><option value="fixed">Fixed</option><option value="verified">Verified</option><option value="closed">Closed</option></select>:<span className="role">{b.status}</span>}</div>):<p className="muted">No bug reports have been submitted.</p>}
 </section>
}