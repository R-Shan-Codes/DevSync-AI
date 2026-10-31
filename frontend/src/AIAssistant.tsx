import { useCallback, useEffect, useState } from 'react'
import { Bot, MessageSquare, Plus, RefreshCw, Send, Trash2 } from 'lucide-react'
import { request } from './api'
type Props = { token: string; projectId: string; assignedRole: string }
type Conversation = { id: string; role: string; title: string; created_at: string; updated_at: string }
type Message = { id: string; sender: 'user' | 'assistant'; content: string; created_at: string }
const roleLabels: Record<string, string> = {
  team_leader_project_manager: 'Team Leader / Project Manager', ui_ux_designer: 'UI/UX Designer',
  frontend_developer: 'Frontend Developer', backend_developer: 'Backend Developer',
  tester_qa_engineer: 'Tester / QA Engineer', devops_engineer: 'DevOps Engineer',
  security_engineer: 'Security Engineer', documentation_specialist: 'Documentation Specialist',
}
export default function AIAssistant({ token, projectId, assignedRole }: Props) {
  const [conversations, setConversations] = useState<Conversation[]>([])
  const [selectedId, setSelectedId] = useState('')
  const [messages, setMessages] = useState<Message[]>([])
  const [prompt, setPrompt] = useState('')
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const loadConversations = useCallback(async () => {
    if (!projectId) { setConversations([]); setSelectedId(''); return }
    try {
      const rows = await request<Conversation[]>(`/projects/${projectId}/ai/conversations`, token)
      setConversations(rows)
      if (!selectedId || !rows.some(row => row.id === selectedId)) setSelectedId(rows[0]?.id || '')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load AI conversations') }
  }, [token, projectId, selectedId])
  useEffect(() => {
    setSelectedId(''); setMessages([]); setConversations([]); setError(''); setNotice('')
    void loadConversations()
  }, [projectId, token])
  const loadMessages = useCallback(async () => {
    if (!projectId || !selectedId) { setMessages([]); return }
    try {
      const rows = await request<Message[]>(`/projects/${projectId}/ai/conversations/${selectedId}/messages`, token)
      setMessages(rows)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load conversation') }
  }, [token, projectId, selectedId])
  useEffect(() => { void loadMessages() }, [loadMessages])
  async function createConversation() {
    setBusy(true); setError('')
    try {
      const row = await request<Conversation>(`/projects/${projectId}/ai/conversations`, token, {
        method: 'POST', body: JSON.stringify({ role: assignedRole, title: 'New conversation' }),
      })
      setConversations(current => [row, ...current]); setSelectedId(row.id); setMessages([])
      setNotice('Conversation created. Messages are saved to your project workspace.')
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not create conversation') }
    finally { setBusy(false) }
  }
  async function sendMessage() {
    const content = prompt.trim()
    if (!content || !selectedId || busy) return
    setBusy(true); setError(''); setNotice(''); setPrompt('')
    try {
      await request<Message>(`/projects/${projectId}/ai/conversations/${selectedId}/messages`, token, {
        method: 'POST', body: JSON.stringify({ content }),
      })
      await loadMessages(); await loadConversations()
    } catch (e) {
      // The API stores the user message before Gemini is called; reload it even on provider errors.
      await loadMessages()
      setError(e instanceof Error ? e.message : 'AI request failed')
    } finally { setBusy(false) }
  }
  async function deleteConversation() {
    if (!selectedId || !window.confirm('Delete this conversation and its messages?')) return
    setBusy(true)
    try {
      await request(`/projects/${projectId}/ai/conversations/${selectedId}`, token, { method: 'DELETE' })
      setSelectedId(''); setMessages([]); await loadConversations()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not delete conversation') }
    finally { setBusy(false) }
  }
  const selected = conversations.find(row => row.id === selectedId)
  return <div className="ai-chat-layout">
    <aside className="panel ai-chat-sidebar">
      <div className="panel-heading"><div><h3>Conversations</h3><p className="muted">Private to your account</p></div>
        <button className="icon-button" title="New conversation" disabled={busy || !projectId} onClick={() => void createConversation()}><Plus size={15}/></button>
      </div>
      {conversations.length ? conversations.map(row => <button key={row.id} className={"ai-conversation " + (row.id === selectedId ? "active" : "")} onClick={() => setSelectedId(row.id)}>
        <MessageSquare size={14}/><span><b>{row.title}</b><small>{new Date(row.updated_at).toLocaleString()}</small></span>
      </button>) : <p className="muted">No saved conversations yet.</p>}
    </aside>
    <section className="panel ai-chat-main">
      <div className="panel-heading">
        <div><h3><Bot size={16}/> AI Role Assistant</h3><p className="muted">{roleLabels[assignedRole] || assignedRole.replaceAll('_', ' ')} · Project-aware persistent chat</p></div>
        <div className="ai-chat-toolbar">
          {selected && <button className="text-button" disabled={busy} onClick={() => void deleteConversation()}><Trash2 size={14}/> Delete</button>}
          <button className="icon-button" disabled={busy || !selectedId} onClick={() => void loadMessages()} title="Refresh messages"><RefreshCw size={14}/></button>
        </div>
      </div>
      {error && <div className="error">{error}</div>}
      {notice && <div className="github-message">{notice}</div>}
      {!selected ? <div className="ai-chat-empty"><Bot size={28}/><b>Start a project-aware conversation</b><p className="muted">Create a conversation to keep your AI assistance and message history.</p><button className="primary" disabled={busy || !projectId} onClick={() => void createConversation()}><Plus size={15}/> New conversation</button></div> :
      <><div className="ai-chat-messages">
        {messages.map(message => <article key={message.id} className={"ai-chat-message " + message.sender}>
          <small>{message.sender === 'assistant' ? 'DevSync AI' : 'You'} · {new Date(message.created_at).toLocaleString()}</small><p>{message.content}</p>
        </article>)}
        {busy && <div className="muted ai-chat-thinking">DevSync AI is processing the project context…</div>}
      </div>
      <div className="ai-chat-compose">
        <textarea rows={3} value={prompt} onChange={event => setPrompt(event.target.value)} onKeyDown={event => { if (event.key === 'Enter' && !event.shiftKey) { event.preventDefault(); void sendMessage() } }} placeholder="Ask about implementation, bugs, tests or delivery…"/>
        <button className="primary" disabled={busy || !prompt.trim()} onClick={() => void sendMessage()}><Send size={15}/> Send</button>
      </div></>}
    </section>
  </div>
}
