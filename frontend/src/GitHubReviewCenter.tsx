import { useEffect, useState } from 'react'
import { AlertTriangle, Bot, GitPullRequest, RefreshCw, ShieldCheck, Sparkles } from 'lucide-react'
import { request } from './api'

type Finding = {
  severity: 'critical'|'high'|'medium'|'low'|'info'
  title: string
  file: string
  line: number|null
  explanation: string
  recommendation: string
  confidence: number
}
type Analysis = {
  id: string
  artifact_type: string
  source_key: string
  summary: string
  findings: Finding[]
  created_at: string
  disclaimer: string
}
type Props = { token: string; projectId: string; canReview: boolean }

const severityClass = (severity: string) => `ai-finding-severity ${severity}`

export default function GitHubReviewCenter({ token, projectId, canReview }: Props) {
  const [pullNumber, setPullNumber] = useState('')
  const [commitSha, setCommitSha] = useState('')
  const [busy, setBusy] = useState<'review'|'checks'|''>('')
  const [error, setError] = useState('')
  const [message, setMessage] = useState('')
  const [analyses, setAnalyses] = useState<Analysis[]>([])
  const [selected, setSelected] = useState<Analysis|null>(null)

  async function refresh() {
    if (!projectId) return
    try {
      const rows = await request<Analysis[]>(`/github/projects/${projectId}/ai-analyses?limit=20`, token)
      setAnalyses(rows)
      if (rows.length && !selected) setSelected(rows[0])
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Unable to load AI review history')
    }
  }

  useEffect(() => {
    setAnalyses([])
    setSelected(null)
    setError('')
    if (projectId) refresh()
  }, [token, projectId])

  async function analyze(kind: 'review'|'checks') {
    if (!projectId) return
    if (kind === 'review' && (!/^\d+$/.test(pullNumber) || Number(pullNumber) < 1)) {
      setError('Enter a valid GitHub pull-request number.')
      return
    }
    if (kind === 'checks' && !/^[0-9a-fA-F]{40,64}$/.test(commitSha)) {
      setError('Enter a full 40- or 64-character commit SHA.')
      return
    }
    setBusy(kind)
    setError('')
    setMessage('')
    try {
      const path = kind === 'review'
        ? `/github/projects/${projectId}/pull-requests/${Number(pullNumber)}/review`
        : `/github/projects/${projectId}/checks/${encodeURIComponent(commitSha)}/analyze`
      const result = await request<Analysis>(path, token, { method: 'POST' })
      setSelected(result)
      setMessage(kind === 'review' ? 'AI pull-request review completed.' : 'CI failure analysis completed.')
      await refresh()
    } catch (e) {
      setError(e instanceof Error ? e.message : 'AI analysis failed')
    } finally {
      setBusy('')
    }
  }

  return <div className="github-ai-center">
    <section className="panel">
      <div className="panel-heading">
        <div><h3><Sparkles size={17}/> AI code review & debugging</h3><p className="muted">Review GitHub pull requests and diagnose failed Actions runs using project-linked repository evidence.</p></div>
        <Bot size={19}/>
      </div>
      <div className="github-ai-actions">
        <div className="github-ai-action">
          <label>Pull request number<input inputMode="numeric" value={pullNumber} onChange={e=>setPullNumber(e.target.value)} placeholder="e.g. 27"/></label>
          <button className="primary" disabled={Boolean(busy)||!projectId||!canReview} onClick={()=>analyze('review')}><GitPullRequest size={15}/>{busy==='review'?'Reviewing…':'Review pull request'}</button>
          {!canReview&&<small className="muted">Your project role needs review permission to run code reviews.</small>}
        </div>
        <div className="github-ai-action">
          <label>Commit SHA<input value={commitSha} onChange={e=>setCommitSha(e.target.value)} placeholder="Full commit SHA"/></label>
          <button className="primary" disabled={Boolean(busy)||!projectId} onClick={()=>analyze('checks')}><ShieldCheck size={15}/>{busy==='checks'?'Analyzing…':'Analyze failed CI'}</button>
          <small className="muted">Finds failed GitHub Actions runs and reviews available job logs.</small>
        </div>
      </div>
      <p className="muted ai-privacy-note">Privacy: the selected pull-request diff or failed workflow logs are sent to the configured Gemini API for analysis. Likely secrets are redacted first; avoid sending credentials or sensitive data. AI findings are advisory and never approve, merge or modify code.</p>
      {error&&<div className="error">{error}</div>}
      {message&&<div className="github-message">{message}</div>}
    </section>
    <section className="panel">
      <div className="panel-heading"><div><h3>Analysis history</h3><p className="muted">Persisted reviews and CI diagnoses for this project.</p></div><button className="icon-button" onClick={refresh} title="Refresh history"><RefreshCw size={15}/></button></div>
      {analyses.length===0?<p className="muted">No AI GitHub analyses yet.</p>:<div className="github-ai-history">{analyses.map(item=><button key={item.id} className={selected?.id===item.id?'github-ai-history-item selected':'github-ai-history-item'} onClick={()=>setSelected(item)}><b>{item.artifact_type==='pull_request_review'?'Pull request review':'CI failure analysis'}</b><small>{item.source_key} · {item.findings.length} finding(s) · {new Date(item.created_at).toLocaleString()}</small></button>)}</div>}
    </section>
    {selected&&<section className="panel">
      <div className="panel-heading"><div><h3>{selected.artifact_type==='pull_request_review'?'Pull request review':'CI failure diagnosis'} · {selected.source_key}</h3><p className="muted">{new Date(selected.created_at).toLocaleString()}</p></div><AlertTriangle size={18}/></div>
      <p className="ai-analysis-summary">{selected.summary}</p>
      {selected.findings.length===0?<div className="github-message">No actionable findings were returned from the supplied evidence.</div>:selected.findings.map((finding,index)=><article className="ai-finding" key={index}>
        <div className="ai-finding-heading"><b>{finding.title}</b><span className={severityClass(finding.severity)}>{finding.severity}</span></div>
        <small>{finding.file||'Workflow evidence'}{finding.line? ` · line ${finding.line}`:''} · {Math.round(finding.confidence*100)}% confidence</small>
        <p>{finding.explanation}</p>
        {finding.recommendation&&<div className="ai-recommendation"><b>Suggested next step</b><p>{finding.recommendation}</p></div>}
      </article>)}
      <p className="muted ai-privacy-note">{selected.disclaimer}</p>
    </section>}
  </div>
}
