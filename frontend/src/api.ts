export const API = import.meta.env.VITE_API_URL || 'http://127.0.0.1:8000/api/v1'
export type Project = {id:string;name:string;description:string;owner_id:string}
export type Task = {id:string;project_id:string;title:string;description:string;status:string;assignee_id:string|null}
export type Activity = {id:string;event_type:string;payload:Record<string,unknown>;created_at:string;actor_id:string}
export type Member = {id:string;user_id:string;email:string;display_name:string;role:string}
export function authHeaders(token:string){return {'Authorization':`Bearer ${token}`,'Content-Type':'application/json'}}
export async function request<T>(path:string,token:string,init:RequestInit={}):Promise<T>{
 const response=await fetch(API+path,{...init,headers:{...authHeaders(token),...(init.headers||{})}})
 if(!response.ok){const body=await response.json().catch(()=>({}));throw new Error(body.detail||`Request failed (${response.status})`)}
 if(response.status===204)return undefined as T
 return response.json()
}