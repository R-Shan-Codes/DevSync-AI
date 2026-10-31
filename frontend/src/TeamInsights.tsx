import { BarChart3, CheckCircle2, CircleDot, ShieldAlert, Users } from 'lucide-react'
import { Member, Task } from './api'
type Props={members:Member[];tasks:Task[]}
const pretty=(s:string)=>s.replaceAll('_',' ').replace(/\b\w/g,c=>c.toUpperCase())
export default function TeamInsights({members,tasks}:Props){
 const complete=['passed','ready_for_merge','merged'];const active=['in_progress','submitted','in_review','approved','ready_for_testing','testing'];
 const rows=members.map(member=>{const assigned=tasks.filter(t=>t.assignee_id===member.user_id);return {member,assigned:assigned.length,completed:assigned.filter(t=>complete.includes(t.status)).length,active:assigned.filter(t=>active.includes(t.status)).length,blocked:assigned.filter(t=>t.status==='failed').length}}).sort((a,b)=>b.completed-a.completed||b.assigned-a.assigned)
 return <section className="panel"><div className="panel-heading"><div><h3>Team contribution intelligence</h3><p className="muted">A task-based view of ownership, delivery and blocked work.</p></div><BarChart3 size={18}/></div>
  <div className="stats-grid"><div className="stat-card"><Users size={18}/><span>Contributors</span><strong>{members.length}</strong></div><div className="stat-card"><CheckCircle2 size={18}/><span>Completed tasks</span><strong>{tasks.filter(t=>complete.includes(t.status)).length}</strong></div><div className="stat-card"><CircleDot size={18}/><span>Active tasks</span><strong>{tasks.filter(t=>active.includes(t.status)).length}</strong></div><div className="stat-card"><ShieldAlert size={18}/><span>Blocked tasks</span><strong>{tasks.filter(t=>t.status==='failed').length}</strong></div></div>
  {rows.length?rows.map(row=><div className="role-task-row" key={row.member.user_id}><div><b>{row.member.display_name}</b><small>{pretty(row.member.role)} · {row.assigned} assigned · {row.completed} completed · {row.active} active · {row.blocked} blocked</small></div><div className="contribution-meter" title={`${row.completed} of ${row.assigned} completed`}><span style={{width:`${row.assigned?Math.round(row.completed/row.assigned*100):0}%`}}/></div></div>):<p className="muted">Add team members to see contribution insights.</p>}
  <p className="muted insight-note">Metrics are derived from DevSync task assignments and statuses; they are not estimates of individual productivity.</p>
 </section>
}