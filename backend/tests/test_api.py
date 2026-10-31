def auth(client,email='dev@example.com'):
 client.post('/api/v1/auth/register',json={'email':email,'display_name':'Dev','password':'secure-pass-123'})
 token=client.post('/api/v1/auth/login',data={'username':email,'password':'secure-pass-123'}).json()['access_token']
 return {'Authorization':f'Bearer {token}'}
def test_auth_project_task_activity(client):
 h=auth(client);assert client.get('/api/v1/auth/me',headers=h).status_code==200
 p=client.post('/api/v1/projects',headers=h,json={'name':'DevSync Project'});assert p.status_code==201
 pid=p.json()['id'];t=client.post(f'/api/v1/projects/{pid}/tasks',headers=h,json={'title':'Implement auth'});assert t.status_code==201
 tid=t.json()['id'];u=client.patch(f'/api/v1/projects/{pid}/tasks/{tid}',headers=h,json={'status':'in_progress'});assert u.status_code==200
 assert len(client.get(f'/api/v1/projects/{pid}/activity',headers=h).json())>=2
def test_duplicate_registration_and_private_project(client):
 h=auth(client);dup=client.post('/api/v1/auth/register',json={'email':'dev@example.com','display_name':'Dev','password':'secure-pass-123'});assert dup.status_code==409
 other=auth(client,'other@example.com');p=client.post('/api/v1/projects',headers=h,json={'name':'Private'}).json()
 assert client.get('/api/v1/projects/'+p['id'],headers=other).status_code==404
