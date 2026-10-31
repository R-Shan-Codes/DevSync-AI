import { useCallback, useEffect, useState } from 'react'
import { Activity, BrainCircuit, Check, GitCommit, RefreshCw, Sparkles, X } from 'lucide-react'
import { request } from './api'

type Props = { token: string; projectId: string; canEdit: boolean }
type Recommendation = { id:string; task_id:string|null; recommendation_type:string; proposed_value:string; rationale:string; evidence:string[]; status:string; created_at:string }
type CommitSuggestion = { commit_hash:string; message:string; author:string; committed_at:string; candidates:{task_id:string;task_title:string;status:string;confidence:number;matched_terms:string[]}[] }

export default function IntelligenceCenter({token,projectId,canEdit}:Props) {
  const [summary,setSummary]=useState<any>(null),[events,setEvents]=useState<any[]>([]),[files,setFiles]=useState<any[]>([])
  const [recommendations,setRecommendations]=useState<Recommendation[]>([]),[commits,setCommits]=useState<CommitSuggestion[]>([])
  const [busy,setBusy]=useState(false),[error,setError]=useState(''),[notice,setNotice]=useState('')
  const load=useCallback(async()=>{
    if(!projectId)return
    setBusy(true);setError('')
    try {
      const [s,e,f,r,c]=await Promise.all([
        request<any>(`/projects/${projectId}/intelligence/summary`,token),
        request<any[]>(`/projects/${projectId}/intelligence/events?limit=30`,token),
        request<any[]>(`/projects/${projectId}/intelligence/files?limit=30`,token),
        request<Recommendation[]>(`/projects/${projectId}/ai/recommendations`,token),
        request<{suggestions:CommitSuggestion[]}>(`/projects/${projectId}/intelligence/commit-task-suggestions`,token)
      ])
      setSummary(s);setEvents(e);setFiles(f);setRecommendations(r);setCommits(c.suggestions)
    } catch(e) { setError(e instanceof Error?e.message:'Unable to load intelligence data') }
    finally { setBusy(false) }
  },[token,projectId])
  useEffect(()=>{void load()},[load])
  async function generate(){
    setBusy(true);setError('');setNotice('')
    try { const result=await request<{generated:number}>(`/projects/${projectId}/ai/task-recommendations`,token,{method:'POST'});setNotice(`Generated ${result.generated} evidence-based recommendation(s). Review them below.`);await load() }
    catch(e){setError(e instanceof Error?e.message:'AI recommendation generation failed')}
    finally{setBusy(false)}
  }
  async function decide(id:string,decision:'accepted'|'rejected'|'modified',replacement?:string){
    try { await request(`/projects/${projectId}/ai/recommendations/${id}/override`,token,{method:'POST',body:JSON.stringify({decision,replacement_value:replacement,reason:'Reviewed in Intelligence Center'})});setNotice(`Recommendation ${decision}.`);await load() }
    catch(e){setError(e instanceof Error?e.message:'Could not record decision')}
  }
  async function linkCommit(commitHash:string,taskId:string,confidence:number){
    try {await request(`/projects/${projectId}/intelligence/commit-links`,token,{method:'POST',body:JSON.stringify({commit_hash:commitHash,task_id:taskId,confidence})});setNotice('Commit linked to task.');await load()}
    catch(e){setError(e instanceof Error?e.message:'Could not link commit')}
  }
  if(!projectId)return <section className="panel muted">Select a project to view development intelligence.</section>
  return <div className="intelligence-center">
    <div className="welcome-row"><div><h1>AI Development Intelligence</h1><p className="muted">Evidence from real project activity, code-change metadata and delivery workflow.</p></div><button className="icon-button" onClick={()=>void load()} disabled={busy}><RefreshCw size={15}/> Refresh</button></div>
    {error&&<div className="error">{error}</div>}{notice&&<div className="intelligence-notice">{notice}</div>}
    {summary&&<div className="stats-grid">{[['Development events',summary.development_events],['File changes',summary.file_changes],['Unique files',summary.unique_files],['Active developers',summary.active_developers],['Pending AI decisions',summary.pending_ai_recommendations]].map(([label,value]:any)=><div className="stat-card" key={label}><span>{label}</span><strong>{value}</strong></div>)}</div>}
    <section className="panel"><div className="panel-heading"><div><h3><BrainCircuit size={16}/> AI task recommendations</h3><p className="muted">Gemini analyzes task state and recent development activity. Nothing changes automatically.</p></div><button className="primary" onClick={()=>void generate()} disabled={busy||!canEdit}><Sparkles size={15}/>{busy?'Analyzing…':'Generate recommendations'}</button></div>
      {!recommendations.length?<p className="muted">No recommendations yet. Generate an analysis after syncing tasks and development activity.</p>:recommendations.map(r=><div className="intelligence-item" key={r.id}><div className="intelligence-item-main"><div><b>{r.recommendation_type.replaceAll('_',' ')} · {r.proposed_value.replaceAll('_',' ')}</b><small>Task: {r.task_id||'Project-wide'} · {new Date(r.created_at).toLocaleString()}</small></div><span className={`status-chip ${r.status}`}>{r.status}</span></div><p>{r.rationale}</p>{r.evidence?.length>0&&<small className="muted">Evidence: {r.evidence.join(' · ')}</small>}{r.status==='pending'&&<div className="intelligence-actions"><button className="text-button" disabled={!canEdit} onClick={()=>void decide(r.id,'accepted')}><Check size={13}/> Accept</button><button className="text-button" disabled={!canEdit} onClick={()=>void decide(r.id,'rejected')}><X size={13}/> Reject</button>{r.recommendation_type==='task_status'&&<button className="text-button" disabled={!canEdit} onClick={()=>{const value=window.prompt('Replacement status:',r.proposed_value);if(value?.trim())void decide(r.id,'modified',value.trim())}}>Modify</button>}</div>}</div>)}
    </section>
    <section className="panel"><div className="panel-heading"><div><h3><GitCommit size={16}/> Commit-to-task matching</h3><p className="muted">Text-overlap candidates from commit messages and task descriptions. Confirm before linking.</p></div></div>
      {!commits.length?<p className="muted">No unlinked commit candidates. Sync GitHub commits and create tasks with meaningful descriptions.</p>:commits.map(c=><div className="intelligence-item" key={c.commit_hash}><b>{c.message}</b><small>{c.author} · {c.commit_hash.slice(0,10)} · {new Date(c.committed_at).toLocaleString()}</small>{c.candidates.map(candidate=><div className="commit-candidate" key={candidate.task_id}><div><b>{candidate.task_title}</b><small>{Math.round(candidate.confidence*100)}% heuristic match · {candidate.matched_terms.join(', ')}</small></div><button className="primary" disabled={!canEdit} onClick={()=>void linkCommit(c.commit_hash,candidate.task_id,candidate.confidence)}>Confirm link</button></div>)}</div>)}
    </section>
    <div className="grid-two"><section className="panel"><div className="panel-heading"><div><h3><Activity size={16}/> Recent development events</h3><p className="muted">Metadata only; source files are never uploaded.</p></div></div>{events.length?events.slice(0,15).map(e=><div className="activity-row" key={e.id}><div className="activity-dot"/><div><b>{e.event_type}</b><small>{JSON.stringify(e.payload)} · {new Date(e.created_at).toLocaleString()}</small></div></div>):<p className="muted">No development events received yet. Open a tracked workspace in the VS Code extension.</p>}</section>
    <section className="panel"><div className="panel-heading"><div><h3>Recent file changes</h3><p className="muted">Paths and change types only.</p></div></div>{files.length?files.slice(0,15).map(f=><div className="activity-row" key={f.id}><div className="activity-dot"/><div><b>{f.path}</b><small>{f.change_type} · {f.branch||'branch unknown'} · {new Date(f.created_at).toLocaleString()}</small></div></div>):<p className="muted">No file changes recorded yet.</p>}</section></div>
  </div>
}
