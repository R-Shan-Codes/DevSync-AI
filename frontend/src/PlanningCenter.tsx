import { useEffect,useMemo,useState } from 'react'
import { CalendarDays,Flag,Layers3,Plus,RefreshCw,Save } from 'lucide-react'
import { Cycle,Milestone,Task,request } from './api'

type View='cycles'|'roadmap'|'hierarchy'
const today=()=>new Date().toISOString().slice(0,10)
const afterDays=(days:number)=>{const d=new Date();d.setDate(d.getDate()+days);return d.toISOString().slice(0,10)}
const done=(status:string)=>['passed','merged','completed'].includes(status)
const pretty=(value:string)=>value.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())

export default function PlanningCenter({token,projectId,tasks,canEdit,revision,onRefresh}:{token:string;projectId:string;tasks:Task[];canEdit:boolean;revision:number;onRefresh:()=>void}){
 const [view,setView]=useState<View>('cycles')
 const [cycles,setCycles]=useState<Cycle[]>([])
 const [milestones,setMilestones]=useState<Milestone[]>([])
 const [loading,setLoading]=useState(false)
 const [error,setError]=useState('')
 const [busy,setBusy]=useState(false)
 const [cycleName,setCycleName]=useState('')
 const [cycleGoal,setCycleGoal]=useState('')
 const [cycleStart,setCycleStart]=useState(today())
 const [cycleEnd,setCycleEnd]=useState(afterDays(13))
 const [milestoneName,setMilestoneName]=useState('')
 const [milestoneDescription,setMilestoneDescription]=useState('')
 const [milestoneDue,setMilestoneDue]=useState('')
 const [selectedTask,setSelectedTask]=useState('')
 const [taskCycle,setTaskCycle]=useState('')
 const [taskMilestone,setTaskMilestone]=useState('')
 const [taskParent,setTaskParent]=useState('')
 const selected=tasks.find(task=>task.id===selectedTask)

 async function load(){
  if(!projectId)return
  setLoading(true);setError('')
  try{
   const [cycleRows,milestoneRows]=await Promise.all([
    request<Cycle[]>(`/projects/${projectId}/cycles`,token),
    request<Milestone[]>(`/projects/${projectId}/milestones`,token)
   ])
   setCycles(cycleRows);setMilestones(milestoneRows)
  }catch(e){setError(e instanceof Error?e.message:'Could not load planning data')}
  finally{setLoading(false)}
 }
 useEffect(()=>{void load()},[projectId,token,revision])
 useEffect(()=>{
  if(!tasks.length){setSelectedTask('');return}
  if(!tasks.some(task=>task.id===selectedTask))setSelectedTask(tasks[0].id)
 },[tasks,selectedTask])
 useEffect(()=>{
  if(!selected)return
  setTaskCycle(selected.cycle_id||'')
  setTaskMilestone(selected.milestone_id||'')
  setTaskParent(selected.parent_task_id||'')
 },[selectedTask,selected?.cycle_id,selected?.milestone_id,selected?.parent_task_id])

 async function createCycle(){
  if(!cycleName.trim())return
  setBusy(true);setError('')
  try{
   await request<Cycle>(`/projects/${projectId}/cycles`,token,{method:'POST',body:JSON.stringify({name:cycleName.trim(),goal:cycleGoal.trim(),start_date:cycleStart,end_date:cycleEnd})})
   setCycleName('');setCycleGoal('');await load();onRefresh()
  }catch(e){setError(e instanceof Error?e.message:'Could not create cycle')}
  finally{setBusy(false)}
 }
 async function updateCycle(cycle:Cycle,patch:Record<string,unknown>){
  setBusy(true);setError('')
  try{await request<Cycle>(`/projects/${projectId}/cycles/${cycle.id}`,token,{method:'PATCH',body:JSON.stringify(patch)});await load();onRefresh()}
  catch(e){setError(e instanceof Error?e.message:'Could not update cycle')}
  finally{setBusy(false)}
 }
 async function createMilestone(){
  if(!milestoneName.trim())return
  setBusy(true);setError('')
  try{
   await request<Milestone>(`/projects/${projectId}/milestones`,token,{method:'POST',body:JSON.stringify({name:milestoneName.trim(),description:milestoneDescription.trim(),due_date:milestoneDue||null})})
   setMilestoneName('');setMilestoneDescription('');setMilestoneDue('');await load();onRefresh()
  }catch(e){setError(e instanceof Error?e.message:'Could not create milestone')}
  finally{setBusy(false)}
 }
 async function updateMilestone(milestone:Milestone,patch:Record<string,unknown>){
  setBusy(true);setError('')
  try{await request<Milestone>(`/projects/${projectId}/milestones/${milestone.id}`,token,{method:'PATCH',body:JSON.stringify(patch)});await load();onRefresh()}
  catch(e){setError(e instanceof Error?e.message:'Could not update milestone')}
  finally{setBusy(false)}
 }
 async function saveTaskLinks(){
  if(!selected)return
  setBusy(true);setError('')
  try{
   await request<Task>(`/projects/${projectId}/tasks/${selected.id}`,token,{method:'PATCH',body:JSON.stringify({cycle_id:taskCycle||null,milestone_id:taskMilestone||null,parent_task_id:taskParent||null})})
   onRefresh()
  }catch(e){setError(e instanceof Error?e.message:'Could not update task planning links')}
  finally{setBusy(false)}
 }
 const cycleProgress=(cycle:Cycle)=>{const related=tasks.filter(task=>task.cycle_id===cycle.id);return {total:related.length,done:related.filter(task=>done(task.status)).length}}
 const milestoneProgress=(milestone:Milestone)=>{const related=tasks.filter(task=>task.milestone_id===milestone.id);return {total:related.length,done:related.filter(task=>done(task.status)).length}}

 return <section className="planning-center">
  <div className="welcome-row"><div><h1>Project planning</h1><p className="muted">Plan delivery cycles, track milestones and organize work into parent tasks and subtasks.</p></div><button className="secondary" onClick={()=>void load()} disabled={loading}><RefreshCw size={14}/> Refresh</button></div>
  <div className="planning-tabs">
   <button className={view==='cycles'?'active':''} onClick={()=>setView('cycles')}><CalendarDays size={14}/> Cycles</button>
   <button className={view==='roadmap'?'active':''} onClick={()=>setView('roadmap')}><Flag size={14}/> Milestones & roadmap</button>
   <button className={view==='hierarchy'?'active':''} onClick={()=>setView('hierarchy')}><Layers3 size={14}/> Task hierarchy</button>
  </div>
  {error&&<div className="error">{error}</div>}
  {view==='cycles'&&<>
   {canEdit&&<section className="panel"><div className="panel-heading"><div><h3>Create a delivery cycle</h3><p className="muted">Define a time-boxed sprint and its outcome.</p></div></div>
    <div className="planning-form-grid">
     <label>Cycle name<input value={cycleName} maxLength={120} placeholder="e.g. Sprint 04" onChange={e=>setCycleName(e.target.value)}/></label>
     <label>Goal<input value={cycleGoal} maxLength={4000} placeholder="What should the team deliver?" onChange={e=>setCycleGoal(e.target.value)}/></label>
     <label>Start date<input type="date" value={cycleStart} onChange={e=>setCycleStart(e.target.value)}/></label>
     <label>End date<input type="date" value={cycleEnd} min={cycleStart} onChange={e=>setCycleEnd(e.target.value)}/></label>
    </div><div className="planning-form-actions"><button className="primary" disabled={busy||!cycleName.trim()||cycleEnd<cycleStart} onClick={createCycle}><Plus size={14}/> Create cycle</button></div>
   </section>}
   <div className="panel-heading"><div><h3>Delivery cycles</h3><p className="muted">{cycles.length} cycle{cycles.length===1?'':'s'} · Work is linked to cycles from task hierarchy.</p></div></div>
   {!cycles.length?<div className="planning-empty">No cycles yet. Create a cycle to start sprint planning.</div>:<div className="planning-card-grid">{cycles.map(cycle=>{const progress=cycleProgress(cycle);return <article className="planning-card" key={cycle.id}>
    <div className="planning-card-header"><div><b>{cycle.name}</b><small>{cycle.start_date} → {cycle.end_date}</small></div><span className="role">{pretty(cycle.status)}</span></div>
    {cycle.goal&&<p>{cycle.goal}</p>}
    <div className="planning-progress-label"><span>{progress.done} of {progress.total} tasks complete</span><b>{progress.total?Math.round(progress.done/progress.total*100):0}%</b></div>
    <div className="planning-progress"><i style={{width:`${progress.total?progress.done/progress.total*100:0}%`}}/></div>
    <small>{progress.total} linked tasks</small>
    {canEdit&&<div className="planning-card-controls"><select aria-label={`Status for ${cycle.name}`} value={cycle.status} disabled={busy} onChange={e=>updateCycle(cycle,{status:e.target.value})}><option value="planned">Planned</option><option value="active">Active</option><option value="completed">Completed</option></select></div>}
   </article>})}</div>}
  </>}
  {view==='roadmap'&&<>
   {canEdit&&<section className="panel"><div className="panel-heading"><div><h3>Add a milestone</h3><p className="muted">Create a release or project outcome with a target date.</p></div></div>
    <div className="planning-form-grid"><label>Milestone name<input value={milestoneName} maxLength={120} placeholder="e.g. Public beta" onChange={e=>setMilestoneName(e.target.value)}/></label><label>Target date<input type="date" value={milestoneDue} onChange={e=>setMilestoneDue(e.target.value)}/></label><label className="wide">Description<input value={milestoneDescription} maxLength={4000} placeholder="What does this milestone include?" onChange={e=>setMilestoneDescription(e.target.value)}/></label></div>
    <div className="planning-form-actions"><button className="primary" disabled={busy||!milestoneName.trim()} onClick={createMilestone}><Plus size={14}/> Add milestone</button></div>
   </section>}
   <div className="panel-heading"><div><h3>Project roadmap</h3><p className="muted">Milestones ordered by target date, with completion based on linked task evidence.</p></div></div>
   {!milestones.length?<div className="planning-empty">No milestones yet. Add the outcomes that define your roadmap.</div>:<div className="planning-card-grid">{milestones.map(milestone=>{const progress=milestoneProgress(milestone);return <article className="planning-card" key={milestone.id}>
    <div className="planning-card-header"><div><b>{milestone.name}</b><small>{milestone.due_date? `Target ${milestone.due_date}`:'No target date'}</small></div><span className="role">{pretty(milestone.status)}</span></div>
    {milestone.description&&<p>{milestone.description}</p>}
    <div className="planning-progress-label"><span>{progress.done} of {progress.total} linked tasks complete</span><b>{progress.total?Math.round(progress.done/progress.total*100):0}%</b></div>
    <div className="planning-progress"><i style={{width:`${progress.total?progress.done/progress.total*100:0}%`}}/></div>
    {canEdit&&<div className="planning-card-controls"><select aria-label={`Status for ${milestone.name}`} value={milestone.status} disabled={busy} onChange={e=>updateMilestone(milestone,{status:e.target.value})}><option value="planned">Planned</option><option value="in_progress">In progress</option><option value="completed">Completed</option></select></div>}
    <div>{tasks.filter(task=>task.milestone_id===milestone.id).map(task=><div className="planning-task-row" key={task.id}><div><b>{task.title}</b><small>{pretty(task.status)}</small></div></div>)}</div>
   </article>})}</div>}
  </>}
  {view==='hierarchy'&&<>
   <section className="panel"><div className="panel-heading"><div><h3>Organize task hierarchy</h3><p className="muted">Assign tasks to a cycle, milestone and optional parent task. Hierarchy cycles are rejected by the API.</p></div></div>
    {!tasks.length?<div className="planning-empty">Create a task before assigning planning relationships.</div>:<>
     <label className="workflow-field">Task<select value={selectedTask} onChange={e=>setSelectedTask(e.target.value)}>{tasks.map(task=><option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
     <div className="planning-relationship-grid">
      <label>Cycle<select value={taskCycle} disabled={!canEdit} onChange={e=>setTaskCycle(e.target.value)}><option value="">No cycle</option>{cycles.map(cycle=><option key={cycle.id} value={cycle.id}>{cycle.name}</option>)}</select></label>
      <label>Milestone<select value={taskMilestone} disabled={!canEdit} onChange={e=>setTaskMilestone(e.target.value)}><option value="">No milestone</option>{milestones.map(milestone=><option key={milestone.id} value={milestone.id}>{milestone.name}</option>)}</select></label>
      <label>Parent task<select value={taskParent} disabled={!canEdit} onChange={e=>setTaskParent(e.target.value)}><option value="">No parent (top-level)</option>{tasks.filter(task=>task.id!==selectedTask).map(task=><option key={task.id} value={task.id}>{task.title}</option>)}</select></label>
      <div className="planning-form-actions"><button className="primary" disabled={!canEdit||busy||!selected} onClick={saveTaskLinks}><Save size={14}/> Save links</button></div>
     </div>
     <div className="panel-heading"><div><h4>Project task hierarchy</h4><p className="muted">Parent tasks and their direct subtasks.</p></div></div>
     {tasks.filter(task=>!task.parent_task_id).map(parent=><div className="planning-task-row" key={parent.id}><div><b>{parent.title}</b><small>{pretty(parent.status)} · {cycles.find(c=>c.id===parent.cycle_id)?.name||'No cycle'} · {milestones.find(m=>m.id===parent.milestone_id)?.name||'No milestone'}</small>{tasks.filter(task=>task.parent_task_id===parent.id).map(child=><div className="planning-task-row" key={child.id}><div><b>↳ {child.title}</b><small>{pretty(child.status)}</small></div></div>)}</div><span className="role">Parent</span></div>)}
    </>}
   </section>
  </>}
  {loading&&<small className="muted">Refreshing planning data…</small>}
 </section>
}
