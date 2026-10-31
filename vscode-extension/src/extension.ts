import * as vscode from 'vscode'
import { DevSyncApi, Task } from './service'

let api: DevSyncApi | undefined
let tree: TaskProvider
let poll: ReturnType<typeof setInterval> | undefined

export function activate(context: vscode.ExtensionContext) {
  api = new DevSyncApi(context)
  tree = new TaskProvider()
  context.subscriptions.push(vscode.window.registerTreeDataProvider('devsync.tasks', tree))
  context.subscriptions.push(vscode.commands.registerCommand('devsync.login', async () => {
    const email = await vscode.window.showInputBox({ prompt: 'DevSync account email', placeHolder: 'you@example.com' })
    const password = await vscode.window.showInputBox({ prompt: 'Password', password: true })
    if (!email || !password) return
    try { await api!.login(email, password); vscode.window.showInformationMessage('Connected to DevSync'); await refresh() }
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
  context.subscriptions.push(vscode.commands.registerCommand('devsync.tasks.open', (task: Task) => vscode.window.showInformationMessage(`${task.title}\nStatus: ${task.status}`)))
  const watcher = vscode.workspace.createFileSystemWatcher('**/*')
  watcher.onDidChange(() => refresh()); watcher.onDidCreate(() => refresh()); watcher.onDidDelete(() => refresh())
  context.subscriptions.push(watcher)
  poll = setInterval(() => refresh(), 60000)
  context.subscriptions.push({ dispose: () => { if (poll) clearInterval(poll) } })
  refresh()
}
async function refresh() { try { if (!api || !(await api.hasToken())) return; tree.setTasks(await api.tasks()); } catch (e) { vscode.window.setStatusBarMessage('DevSync: unable to refresh tasks', 5000) } }
async function syncGit() { try { const result = await api!.syncGit(); vscode.window.showInformationMessage(`DevSync synced ${result.length} new commits`) } catch (e) { vscode.window.showErrorMessage(message(e)) } }
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
export function deactivate() { if (poll) clearInterval(poll) }