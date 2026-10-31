import { useState } from 'react'
import { ArrowRight, Workflow } from 'lucide-react'
import { Member, Task, request } from './api'
type Props={token:string;projectId:string;member:Member|null;tasks:Task[];onRefresh:()=>void}
const transitions:Record<string,string[]>={backlog:['in_progress','cancelled'],in_progress:['submitted','cancelled'],submitted:['in_review','in_progress'],in_review:['approved','in_progress'],approved:['ready_for_testing'],ready_for_testing:['testing'],testing:['passed','failed'],failed:['in_progress'],passed:['ready_for_merge'],ready_for_merge:['merged']}
const pretty=(v:string)=>v.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())
export default function TaskWorkflow({token,projectId,member,tasks,onRefresh}:Props){
 const [busy,setBusy]=useState('');const [message,setMessage]=useState('')
 function allowed(status:string){return (transitions[status]||[]).filter(next=>{if(next==='in_review')return Boolean(member?.permissions.review);if(next==='approved')return Boolean(member?.permissions.approve);if(next==='merged')return Boolean(member?.permissions.merge);if(next==='cancelled')return Boolean(member?.permissions.manage_team);return Boolean(member?.permissions.edit)})}
 async function move(task:Task,status:string){setBusy(task.id);setMessage('');try{await request<Task>(`/projects/${projectId}/tasks/${task.id}`,token,{method:'PATCH',body:JSON.stringify({status})});setMessage(`${task.title}: moved to ${pretty(status)}.`);onRefresh()}catch(e){setMessage(e instanceof Error?e.message:'Could not update task')}finally{setBusy('')}}
 return <section className="panel"><div className="panel-heading"><div><h3>Smart development pipeline</h3><p className="muted">Move work through coding, review, QA and merge using validated transitions.</p></div><Workflow size={18}/></div>
  {message&&<p className="muted">{message}</p>}{tasks.length?tasks.map(task=>{const options=allowed(task.status);return <div className="role-task-row" key={task.id}><div><b>{task.title}</b><small>{pretty(task.status)}</small></div><div className="workflow-action"><select aria-label={`Next status for ${task.title}`} defaultValue="" disabled={!options.length||busy===task.id} onChange={e=>{const next=e.target.value;if(next)move(task,next);e.target.value=''}}><option value="">{options.length?'Move to…':'No permitted next step'}</option>{options.map(s=><option key={s} value={s}>{pretty(s)}</option>)}</select>{options.length>0&&<ArrowRight size={15}/>}</div></div>}) : <p className="muted">No project tasks yet.</p>}
 </section>
}