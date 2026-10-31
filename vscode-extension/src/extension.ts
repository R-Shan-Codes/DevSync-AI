import * as vscode from 'vscode'
import { execFile } from 'child_process'
import { promisify } from 'util'
import { DevEvent, DevSyncApi, Task } from './service'

let api: DevSyncApi | undefined
let tree: TaskProvider
let poll: ReturnType<typeof setInterval> | undefined
let eventTimer: ReturnType<typeof setTimeout> | undefined
let gitPoll: ReturnType<typeof setInterval> | undefined
let lastGitBranch = ''
let lastGitCommit = ''
let flushingEvents = false
const execFileAsync = promisify(execFile)
let pendingEvents: DevEvent[] = []
const MAX_PENDING_EVENTS = 1000

export function activate(context: vscode.ExtensionContext) {
  api = new DevSyncApi(context)
  tree = new TaskProvider()
  context.subscriptions.push(vscode.window.registerTreeDataProvider('devsync.tasks', tree))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.login', async () => {
    const email = await vscode.window.showInputBox({ prompt: 'DevSync account email', placeHolder: 'you@example.com' })
    const password = await vscode.window.showInputBox({ prompt: 'Password', password: true })
    if (!email || !password) return
    try { await api!.login(email, password); vscode.window.showInformationMessage('Connected to DevSync'); void flushDevEvents(); void syncGitMetadata(); await refresh() }
    catch (e) { vscode.window.showErrorMessage(message(e)) }
  }))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.refresh', refresh))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.setRole', async () => {
    try {
      const membership = await api!.membership()
      const enabled = Object.entries(membership.permissions).filter(([, allowed]) => allowed).map(([name]) => name.replaceAll('_', ' ')).join(', ')
      vscode.window.showInformationMessage(`DevSync project role: ${membership.role.replaceAll('_', ' ')}. Permissions: ${enabled}`)
    } catch (e) { vscode.window.showErrorMessage(message(e)) }
  }))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.selectProject', async () => {
    const current = vscode.workspace.getConfiguration('devsync').get<string>('projectId', '')
    const projectId = await vscode.window.showInputBox({ prompt: 'Enter the DevSync project ID', value: current, ignoreFocusOut: true })
    if (!projectId?.trim()) return
    await vscode.workspace.getConfiguration('devsync').update('projectId', projectId.trim(), vscode.ConfigurationTarget.Workspace)
    await refresh()
    vscode.window.showInformationMessage('DevSync project selected')
  }))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.openDashboard', () => vscode.env.openExternal(vscode.Uri.parse(api!.dashboardUrl))))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.syncGit', syncGit))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.githubStatus', githubStatus))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.syncGitHub', syncGitHub))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.tasks.open', (task: Task) => vscode.window.showInformationMessage(`${task.title}\nStatus: ${task.status}`)))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.tasks.changeStatus', async (task: Task) => {
    if (!task) return
    const next: Record<string,string[]> = {backlog:['in_progress','cancelled'],in_progress:['submitted','cancelled'],submitted:['in_review','in_progress'],in_review:['approved','in_progress'],approved:['ready_for_testing'],ready_for_testing:['testing'],testing:['passed','failed'],failed:['in_progress'],passed:['ready_for_merge'],ready_for_merge:['merged']}
    const choices=(next[task.status]||[]).map(value=>({label:value.replaceAll('_',' '),value}))
    if(!choices.length){vscode.window.showInformationMessage('No next workflow stage is available for this task.');return}
    const selected=await vscode.window.showQuickPick(choices,{placeHolder:'Select the next task status'})
    if(!selected)return
    try{await api!.updateTaskStatus(task.id,selected.value);vscode.window.showInformationMessage(`Task moved to ${selected.value.replaceAll('_',' ')}`);await refresh()}catch(e){vscode.window.showErrorMessage(message(e))}
  }))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.tasks.reportBug', async (task: Task) => {
    if(!task)return
    const title=await vscode.window.showInputBox({prompt:'Bug title',placeHolder:'Short description of the defect',ignoreFocusOut:true})
    if(!title?.trim())return
    const description=await vscode.window.showInputBox({prompt:'Steps to reproduce and observed behavior',placeHolder:'Expected result, actual result, reproduction steps',ignoreFocusOut:true})
    if(!description?.trim())return
    const severity=await vscode.window.showQuickPick(['low','medium','high','critical'],{placeHolder:'Select bug severity'})
    if(!severity)return
    try{await api!.reportBug(task.id,title.trim(),description.trim(),severity);vscode.window.showInformationMessage('Bug report submitted to DevSync');await refresh()}catch(e){vscode.window.showErrorMessage(message(e))}
  }))
  const folders = vscode.workspace.workspaceFolders
  if (folders?.length) {
    enqueueEvent({ event_type: 'workspace.opened', payload: { workspace: folders[0].name }, source: 'vscode' })
    void flushDevEvents()
  }
  void syncGitMetadata()
  gitPoll = setInterval(() => { void syncGitMetadata() }, 15000)
  context.subscriptions.push({ dispose: () => { if (gitPoll) clearInterval(gitPoll) } })
  context.subscriptions.push(vscode.workspace.onDidChangeWorkspaceFolders(() => {
    lastGitBranch = ''
    lastGitCommit = ''
    void syncGitMetadata()
  }))

  const watcher = vscode.workspace.createFileSystemWatcher('**/*')
  watcher.onDidChange(uri => queueFileEvent('file.changed', uri))
  watcher.onDidCreate(uri => queueFileEvent('file.created', uri))
  watcher.onDidDelete(uri => queueFileEvent('file.deleted', uri))
  context.subscriptions.push(watcher)
  context.subscriptions.push({ dispose: () => { if (eventTimer) clearTimeout(eventTimer); void flushDevEvents() } })
  poll = setInterval(() => refresh(), 20000)
  context.subscriptions.push({ dispose: () => { if (poll) clearInterval(poll) } })
  refresh()
}
async function refresh() { try { if (!api || !(await api.hasToken())) return; tree.setTasks(await api.tasks()); } catch (e) { vscode.window.setStatusBarMessage('DevSync: unable to refresh tasks', 5000) } }
async function syncGit() { try { const result = await api!.syncGit(); vscode.window.showInformationMessage(`DevSync synced ${result.length} local commits`) } catch (e) { vscode.window.showErrorMessage(message(e)) } }
async function githubStatus() { try { const account = await api!.githubAccount(); vscode.window.showInformationMessage(account.connected ? `GitHub connected as @${account.login}` : 'GitHub is not connected. Connect it from the DevSync dashboard.') } catch (e) { vscode.window.showErrorMessage(message(e)) } }
async function syncGitHub() { try { const result = await api!.syncGitHub(); vscode.window.showInformationMessage(`Synced ${result.new_commits} commits from ${result.repository}`); await refresh() } catch (e) { vscode.window.showErrorMessage(message(e)) } }
function queueFileEvent(event_type: string, uri: vscode.Uri) {
  const path = vscode.workspace.asRelativePath(uri, false).split(String.fromCharCode(92)).join('/')
  const ignored = new Set(['.git', 'node_modules', '.venv', 'venv', 'dist', 'build', 'coverage', '.next'])
  if (!path || path.split('/').some(part => ignored.has(part)) || path.startsWith('../')) return
  enqueueEvent({ event_type, payload: { path }, source: 'vscode' })
  if (pendingEvents.length >= 100) void flushDevEvents()
  if (eventTimer) clearTimeout(eventTimer)
  eventTimer = setTimeout(() => { void flushDevEvents() }, 1200)
}

function enqueueEvent(event: DevEvent) {
  if (event.event_type.startsWith('file.')) {
    const path = String(event.payload.path || '')
    const existing = pendingEvents.findIndex(item =>
      item.event_type === event.event_type && String(item.payload.path || '') === path
    )
    if (existing >= 0) {
      pendingEvents[existing] = event
      return
    }
  }
  if (pendingEvents.length >= MAX_PENDING_EVENTS) {
    const discard = pendingEvents.findIndex(item => item.event_type.startsWith('file.'))
    if (discard >= 0) pendingEvents.splice(discard, 1)
    else if (event.event_type.startsWith('file.')) return
    else pendingEvents.shift()
    vscode.window.setStatusBarMessage('DevSync: offline activity queue reached its limit; oldest metadata was discarded', 7000)
  }
  pendingEvents.push(event)
}

function restoreEvents(batch: DevEvent[]) {
  pendingEvents.unshift(...batch)
  while (pendingEvents.length > MAX_PENDING_EVENTS) {
    const discard = pendingEvents.findIndex(item => item.event_type.startsWith('file.'))
    pendingEvents.splice(discard >= 0 ? discard : 0, 1)
  }
}

async function syncGitMetadata() {
  const folder = vscode.workspace.workspaceFolders?.[0]
  if (!folder || !api || !(await api.hasToken())) return
  const root = folder.uri.fsPath
  try {
    const branchResult = await execFileAsync('git', ['-C', root, 'rev-parse', '--abbrev-ref', 'HEAD'], { timeout: 5000, maxBuffer: 1024 * 1024 })
    const branch = branchResult.stdout.trim()
    if (branch && branch !== lastGitBranch) {
      lastGitBranch = branch
      enqueueEvent({ event_type: 'branch.changed', payload: { branch, repository_path: folder.name }, source: 'vscode' })
    }
    const logResult = await execFileAsync('git', [
      '-C', root, 'log', '-n', '20', '--format=%H%x1f%an%x1f%ae%x1f%cI%x1f%s'
    ], { timeout: 5000, maxBuffer: 1024 * 1024 })
    const recent = logResult.stdout.trim().split(/\r?\n/).filter(Boolean).map(line => {
      const [commitHash, author, authorEmail, committedAt, ...messageParts] = line.split('\x1f')
      return { commitHash, author, authorEmail, committedAt, message: messageParts.join('\x1f') }
    })
    const fresh = []
    for (const commit of recent) {
      if (commit.commitHash === lastGitCommit) break
      if (/^[0-9a-f]{40}$/i.test(commit.commitHash || '')) fresh.push(commit)
    }
    // On first connection, register the current HEAD only; do not import repository history implicitly.
    if (!lastGitCommit && fresh.length > 1) fresh.splice(1)
    for (const commit of fresh.reverse()) {
      enqueueEvent({
        event_type: 'commit.created',
        payload: {
          commit_hash: commit.commitHash.toLowerCase(),
          message: commit.message,
          author: commit.author,
          author_email: commit.authorEmail,
          committed_at: commit.committedAt,
          branch,
          repository_path: folder.name,
        },
        source: 'vscode',
      })
    }
    if (recent[0]?.commitHash) lastGitCommit = recent[0].commitHash
    if (pendingEvents.length) await flushDevEvents()
  } catch {
    // A workspace without Git, or a temporarily unavailable Git executable, is not an extension error.
  }
}

async function flushDevEvents() {
  if (eventTimer) clearTimeout(eventTimer)
  eventTimer = undefined
  if (flushingEvents || !api || !pendingEvents.length) return
  flushingEvents = true
  const batch = pendingEvents.splice(0, 100)
  try {
    if (!(await api.hasToken())) {
      restoreEvents(batch)
      return
    }
    await api.ingestEvents(batch)
  } catch {
    restoreEvents(batch)
    vscode.window.setStatusBarMessage('DevSync: development activity could not be synchronized; retrying', 5000)
    eventTimer = setTimeout(() => { void flushDevEvents() }, 5000)
  } finally {
    flushingEvents = false
  }
  if (pendingEvents.length && !eventTimer) void flushDevEvents()
}

function message(e: unknown) { return e instanceof Error ? e.message : String(e) }
class TaskProvider implements vscode.TreeDataProvider<TaskItem> {
  private emitter = new vscode.EventEmitter<TaskItem | undefined>()
  readonly onDidChangeTreeData = this.emitter.event
  private items: Task[] = []
  setTasks(items: Task[]) { this.items = items; this.refresh() }
  refresh() { this.emitter.fire(undefined) }
  getTreeItem(item: TaskItem) { return item }
  getChildren() { return Promise.resolve(this.items.map(task => new TaskItem(task))) }
}
class TaskItem extends vscode.TreeItem {
  constructor(public readonly task: Task) {
    super(task.title, vscode.TreeItemCollapsibleState.None)
    this.description = task.status.replaceAll('_',' ')
    this.tooltip = task.description
    this.contextValue = 'devsyncTask'
    this.command = { command: 'devsync.tasks.open', title: 'Open task', arguments: [task] }
    this.iconPath = new vscode.ThemeIcon(task.status === 'merged' || task.status === 'passed' ? 'check' : task.status === 'failed' ? 'error' : 'circle-outline')
  }
}
export function deactivate() { if (poll) clearInterval(poll); if (gitPoll) clearInterval(gitPoll); if (eventTimer) clearTimeout(eventTimer); void flushDevEvents() }