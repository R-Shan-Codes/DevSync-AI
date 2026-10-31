export const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1'
export type Project = {id:string;name:string;description:string;owner_id:string;github_repo_full_name?:string|null;github_repo_url?:string|null;github_default_branch?:string|null}
export type Task = {id:string;project_id:string;title:string;description:string;status:string;assignee_id:string|null;priority:string;due_date:string|null}
export type Activity = {id:string;event_type:string;payload:Record<string,unknown>;created_at:string;actor_id:string}
export type Member = {id:string;user_id:string;email:string;display_name:string;role:string;permissions:Record<string,boolean>}
export function authHeaders(token:string){return {'Authorization':`Bearer ${token}`,'Content-Type':'application/json'}}
export async function request<T>(path:string,token:string,init:RequestInit={}):Promise<T>{
 const response=await fetch(API+path,{...init,headers:{...authHeaders(token),...(init.headers||{})}})
 if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||`Request failed (${response.status})`)}
 if(response.status===204)return undefined as T
 return response.json()
}
export type TaskComment = {id:string;project_id:string;task_id:string;author_id:string;body:string;created_at:string}
