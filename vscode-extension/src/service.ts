import * as vscode from 'vscode'
export type Task = {id:string;title:string;description:string;status:string;assignee_id:string|null}
export type Membership = {role:string;permissions:Record<string,boolean>}
export class DevSyncApi {
  constructor(private context:vscode.ExtensionContext) {}
  async hasToken(): Promise<boolean> { return Boolean(await this.context.secrets.get('devsync.token')) }
  get base() { return vscode.workspace.getConfiguration('devsync').get<string>('apiUrl','http://127.0.0.1:8000/api/v1').replace(/\/$/,'') }
  get dashboardUrl() { return this.base.replace(/\/api\/v1$/,'').replace('127.0.0.1','localhost') }
  private async token() { return await this.context.secrets.get('devsync.token') }
  async login(email:string,password:string) {
    const body = new URLSearchParams({username:email,password})
    const response = await fetch(this.base+'/auth/login',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body})
    const data = await response.json() as {access_token?:string;detail?:string}
    if(!response.ok || !data.access_token) throw new Error(data.detail || 'Login failed')
    await this.context.secrets.store('devsync.token',data.access_token)
  }
  private async request<T>(path:string,init:RequestInit={}):Promise<T> {
    const token=await this.token()
    if(!token) throw new Error('Connect your DevSync account first: DevSync: Connect Account')
    const response=await fetch(this.base+path,{...init,headers:{Authorization:`Bearer ${token}`,'Content-Type':'application/json',...(init.headers||{})}})
    const data=await response.json().catch(()=>({})) as any
    if(!response.ok) throw new Error(data.detail || `DevSync API error ${response.status}`)
    return data as T
  }
  private projectId() { return vscode.workspace.getConfiguration('devsync').get<string>('projectId','').trim() }
  async membership():Promise<Membership> { const project=this.projectId();if(!project)throw new Error('Set devsync.projectId in workspace settings first');return this.request(`/projects/${project}/members/me`) }
  async tasks():Promise<Task[]> { const project=this.projectId();if(!project)return [];const member=await this.membership();if(!member.permissions.view)throw new Error('Your DevSync role does not have View permission for this project');return this.request(`/projects/${project}/tasks`) }
  async syncGit():Promise<any[]> {
    const project=this.projectId()
    if(!project) throw new Error('Set devsync.projectId in workspace settings first')
    const member=await this.membership()
    if(!member.permissions.view) throw new Error('Your DevSync role does not have View permission for this project')
    const folders=vscode.workspace.workspaceFolders
    if(!folders?.length) throw new Error('Open a Git workspace folder first')
    const root=folders[0].uri.fsPath
    const workspaceRoot=vscode.workspace.getConfiguration('devsync').get<string>('workspaceRoot','')
    const relative=root.replace(/\\/g,'/').split('/').pop() || root
    return this.request(`/projects/${project}/git/sync`,{method:'POST',body:JSON.stringify({repository_path:workspaceRoot ? relative : root,commit_limit:30})})
  }
}