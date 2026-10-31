import json
from fastapi import HTTPException
PERMISSIONS=("view","edit","create_branch","commit","push","pull","review","approve","merge","deploy","manage_team")
ROLES={"team_leader_project_manager":"Team Leader / Project Manager","ui_ux_designer":"UI/UX Designer","frontend_developer":"Frontend Developer","backend_developer":"Backend Developer","tester_qa_engineer":"Tester / QA Engineer","devops_engineer":"DevOps Engineer","security_engineer":"Security Engineer","documentation_specialist":"Documentation Specialist"}
ALL={p:True for p in PERMISSIONS}
DEFAULTS={"team_leader_project_manager":ALL,"ui_ux_designer":dict(view=True,edit=True,create_branch=True,commit=True,push=False,pull=True,review=True,approve=False,merge=False,deploy=False,manage_team=False),"frontend_developer":dict(view=True,edit=True,create_branch=True,commit=True,push=True,pull=True,review=True,approve=False,merge=False,deploy=False,manage_team=False),"backend_developer":dict(view=True,edit=True,create_branch=True,commit=True,push=True,pull=True,review=True,approve=False,merge=False,deploy=False,manage_team=False),"tester_qa_engineer":dict(view=True,edit=True,create_branch=True,commit=True,push=False,pull=True,review=True,approve=False,merge=False,deploy=False,manage_team=False),"devops_engineer":dict(view=True,edit=True,create_branch=True,commit=True,push=True,pull=True,review=True,approve=False,merge=False,deploy=True,manage_team=False),"security_engineer":dict(view=True,edit=True,create_branch=True,commit=True,push=False,pull=True,review=True,approve=True,merge=False,deploy=False,manage_team=False),"documentation_specialist":dict(view=True,edit=True,create_branch=True,commit=True,push=False,pull=True,review=True,approve=False,merge=False,deploy=False,manage_team=False)}
LEGACY={"administrator":"team_leader_project_manager","coder":"frontend_developer","debugger":"backend_developer","tester":"tester_qa_engineer"}
def normalize_role(role):
 value=role.value if hasattr(role,"value") else str(role)
 return LEGACY.get(value,value)
def permissions_for(member):
 role=normalize_role(member.role);base=DEFAULTS.get(role,DEFAULTS["frontend_developer"]).copy()
 try:
  overrides=json.loads(member.permissions or "{}")
  if isinstance(overrides,dict):
   for key,value in overrides.items():
    if key in PERMISSIONS and isinstance(value,bool): base[key]=value
 except (TypeError,ValueError): pass
 return base
def require_permission(member,permission):
 if permission not in PERMISSIONS or not permissions_for(member).get(permission,False):
  raise HTTPException(status_code=403,detail=f"Your project permissions do not allow: {permission.replace('_',' ')}")
 return member
