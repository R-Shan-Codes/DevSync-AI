import { useCallback, useEffect, useState } from 'react'
import { Bell, CheckCheck, ExternalLink, RefreshCw } from 'lucide-react'
import { request } from './api'

type Props = { token: string; revision: number; onUnreadCount: (count: number) => void; onOpenTask: (resourcePath: string) => void }
type NotificationItem = {
  id: string; project_id: string; project_name: string; actor_id: string | null
  type: string; title: string; message: string; resource_path: string
  read_at: string | null; created_at: string
}
type Inbox = { items: NotificationItem[]; unread_count: number }

export default function NotificationCenter({ token, revision, onUnreadCount, onOpenTask }: Props) {
  const [items, setItems] = useState<NotificationItem[]>([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const load = useCallback(async () => {
    setBusy(true); setError('')
    try {
      const result = await request<Inbox>('/notifications?limit=100', token)
      setItems(result.items)
      onUnreadCount(result.unread_count)
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not load notifications') }
    finally { setBusy(false) }
  }, [token, onUnreadCount])
  useEffect(() => { void load() }, [load, revision])

  async function markRead(id: string) {
    try {
      await request(`/notifications/${id}/read`, token, { method: 'PATCH' })
      await load()
    } catch (e) { setError(e instanceof Error ? e.message : 'Could not update notification') }
  }
  async function markAllRead() {
    setBusy(true)
    try { await request('/notifications/read-all', token, { method: 'POST' }); await load() }
    catch (e) { setError(e instanceof Error ? e.message : 'Could not mark notifications read') }
    finally { setBusy(false) }
  }

  return <section className="panel notification-center">
    <div className="panel-heading">
      <div><h3><Bell size={16}/> Notifications</h3><p className="muted">Task assignments and delivery updates for your account.</p></div>
      <div className="notification-actions">
        <button className="text-button" disabled={busy || !items.some(item => !item.read_at)} onClick={() => void markAllRead()}><CheckCheck size={14}/> Mark all read</button>
        <button className="icon-button" disabled={busy} onClick={() => void load()} title="Refresh"><RefreshCw size={14}/></button>
      </div>
    </div>
    {error && <div className="error">{error}</div>}
    {items.length ? items.map(item => <article key={item.id} className={"notification-item " + (item.read_at ? "read" : "unread")}>
      <span className="notification-indicator"/>
      <div className="notification-content">
        <div className="notification-title-row"><b>{item.title}</b><small>{new Date(item.created_at).toLocaleString()}</small></div>
        <small className="muted">{item.project_name} · {item.type.replaceAll('_', ' ')}</small>
        <p>{item.message}</p>
        <div className="notification-row-actions">
          {!item.read_at && <button className="text-button" onClick={() => void markRead(item.id)}>Mark read</button>}
          {item.resource_path && <button className="text-button" onClick={() => { if (!item.read_at) void markRead(item.id); onOpenTask(item.resource_path) }}><ExternalLink size={13}/> Open task</button>}
        </div>
      </div>
    </article>) : <div className="notification-empty"><Bell size={24}/><b>You're all caught up</b><p className="muted">Task assignments and workflow updates will appear here.</p></div>}
  </section>
}
