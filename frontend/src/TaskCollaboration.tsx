import { useEffect,useState } from 'react'
import { Task,TaskComment,request } from './api'

export default function TaskCollaboration({token,projectId,tasks,canEdit,onRefresh}:{token:string;projectId:string;tasks:Task[];canEdit:boolean;onRefresh:()=>void}){
 const [taskId,setTaskId]=useState('')
 const [priority,setPriority]=useState('medium')
 const [dueDate,setDueDate]=useState('')
 const [comments,setComments]=useState<TaskComment[]>([])
 const [draft,setDraft]=useState('')
 const [error,setError]=useState('')
 const [busy,setBusy]=useState(false)
 const selected=tasks.find(task=>task.id===taskId)
 useEffect(()=>{if(!tasks.length){setTaskId('');return}if(!tasks.some(task=>task.id===taskId))setTaskId(tasks[0].id)},[tasks,taskId])
 useEffect(()=>{if(!selected)return;setPriority(selected.priority||'medium');setDueDate(selected.due_date||'');setError('');request<TaskComment[]>(`/projects/${projectId}/tasks/${selected.id}/comments`,token).then(setComments).catch(e=>setError(e instanceof Error?e.message:'Could not load comments'))},[token,projectId,taskId])
 async function saveMetadata(){if(!selected)return;setBusy(true);setError('');try{await request(`/projects/${projectId}/tasks/${selected.id}`,token,{method:'PATCH',body:JSON.stringify({priority,due_date:dueDate||null})});onRefresh()}catch(e){setError(e instanceof Error?e.message:'Could not save task details')}finally{setBusy(false)}}
 async function addComment(){if(!selected||!draft.trim())return;setBusy(true);setError('');try{const created=await request<TaskComment>(`/projects/${projectId}/tasks/${selected.id}/comments`,token,{method:'POST',body:JSON.stringify({body:draft.trim()})});setComments(current=>[...current,created]);setDraft('')}catch(e){setError(e instanceof Error?e.message:'Could not post comment')}finally{setBusy(false)}}
 return <section className="panel task-collaboration"><div className="panel-heading"><div><h3>Task details & discussion</h3><p className="muted">Set task priority and due date, then keep decisions with the task.</p></div></div>{!tasks.length?<p className="muted">Create a task to start its discussion.</p>:<><div className="task-collaboration-controls"><select aria-label="Select task" value={taskId} onChange={e=>setTaskId(e.target.value)}>{tasks.map(task=><option key={task.id} value={task.id}>{task.title}</option>)}</select><select aria-label="Task priority" value={priority} disabled={!canEdit} onChange={e=>setPriority(e.target.value)}><option value="low">Low priority</option><option value="medium">Medium priority</option><option value="high">High priority</option><option value="urgent">Urgent priority</option></select><input aria-label="Task due date" type="date" value={dueDate} disabled={!canEdit} onChange={e=>setDueDate(e.target.value)}/><button className="primary" disabled={!canEdit||busy} onClick={saveMetadata}>Save details</button></div><div className="task-comments"><h4>Discussion</h4>{comments.map(comment=><article className="task-comment" key={comment.id}><small>{comment.author_id.slice(0,8)} · {new Date(comment.created_at).toLocaleString()}</small><p>{comment.body}</p></article>)}{!comments.length&&<p className="muted">No comments yet.</p>}<div className="task-comment-compose"><input value={draft} maxLength={5000} placeholder="Add a task comment…" onChange={e=>setDraft(e.target.value)} disabled={!canEdit}/><button className="primary" onClick={addComment} disabled={!canEdit||busy||!draft.trim()}>Comment</button></div></div></>}{error&&<div className="error">{error}</div>}</section>
}
