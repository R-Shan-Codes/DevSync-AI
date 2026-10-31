def auth(client,email='planner@example.com'):
    client.post('/api/v1/auth/register',json={'email':email,'display_name':'Planner','password':'secure-pass-123'})
    token=client.post('/api/v1/auth/login',data={'username':email,'password':'secure-pass-123'}).json()['access_token']
    return {'Authorization':f'Bearer {token}'}


def create_project(client,headers,name='Planning project'):
    response=client.post('/api/v1/projects',headers=headers,json={'name':name})
    assert response.status_code==201
    return response.json()


def test_cycles_milestones_and_task_hierarchy_are_persisted(client):
    headers=auth(client)
    project=create_project(client,headers)
    project_id=project['id']

    cycle_response=client.post(
        f'/api/v1/projects/{project_id}/cycles',
        headers=headers,
        json={'name':'Sprint 01','goal':'Deliver planning foundations','start_date':'2026-11-01','end_date':'2026-11-14'},
    )
    assert cycle_response.status_code==201
    cycle=cycle_response.json()
    assert cycle['status']=='planned'

    milestone_response=client.post(
        f'/api/v1/projects/{project_id}/milestones',
        headers=headers,
        json={'name':'Private beta','description':'First integrated release','due_date':'2026-12-01'},
    )
    assert milestone_response.status_code==201
    milestone=milestone_response.json()

    parent=client.post(
        f'/api/v1/projects/{project_id}/tasks',
        headers=headers,
        json={'title':'Build planning module','cycle_id':cycle['id'],'milestone_id':milestone['id']},
    )
    assert parent.status_code==201
    parent_task=parent.json()
    assert parent_task['cycle_id']==cycle['id']
    assert parent_task['milestone_id']==milestone['id']

    child=client.post(
        f'/api/v1/projects/{project_id}/tasks',
        headers=headers,
        json={'title':'Build cycle editor','parent_task_id':parent_task['id'],'cycle_id':cycle['id']},
    )
    assert child.status_code==201
    child_task=child.json()
    assert child_task['parent_task_id']==parent_task['id']

    updated_cycle=client.patch(
        f"/api/v1/projects/{project_id}/cycles/{cycle['id']}",
        headers=headers,
        json={'status':'active'},
    )
    assert updated_cycle.status_code==200
    assert updated_cycle.json()['status']=='active'

    updated_milestone=client.patch(
        f"/api/v1/projects/{project_id}/milestones/{milestone['id']}",
        headers=headers,
        json={'status':'in_progress'},
    )
    assert updated_milestone.status_code==200
    assert updated_milestone.json()['status']=='in_progress'

    assert len(client.get(f'/api/v1/projects/{project_id}/cycles',headers=headers).json())==1
    assert len(client.get(f'/api/v1/projects/{project_id}/milestones',headers=headers).json())==1
    tasks=client.get(f'/api/v1/projects/{project_id}/tasks',headers=headers).json()
    assert {task['id'] for task in tasks}=={parent_task['id'],child_task['id']}


def test_planning_rejects_invalid_dates_and_cross_project_links(client):
    owner=auth(client,'owner@example.com')
    other=auth(client,'other@example.com')
    project=create_project(client,owner,'Owner project')
    other_project=create_project(client,other,'Other project')
    project_id=project['id']

    invalid_cycle=client.post(
        f'/api/v1/projects/{project_id}/cycles',
        headers=owner,
        json={'name':'Bad dates','start_date':'2026-11-20','end_date':'2026-11-01'},
    )
    assert invalid_cycle.status_code==422

    foreign_cycle=client.post(
        f"/api/v1/projects/{other_project['id']}/cycles",
        headers=other,
        json={'name':'Foreign cycle','start_date':'2026-11-01','end_date':'2026-11-10'},
    ).json()
    foreign_milestone=client.post(
        f"/api/v1/projects/{other_project['id']}/milestones",
        headers=other,
        json={'name':'Foreign milestone'},
    ).json()

    invalid_task=client.post(
        f'/api/v1/projects/{project_id}/tasks',
        headers=owner,
        json={'title':'Wrong project cycle','cycle_id':foreign_cycle['id']},
    )
    assert invalid_task.status_code==400

    invalid_milestone_task=client.post(
        f'/api/v1/projects/{project_id}/tasks',
        headers=owner,
        json={'title':'Wrong project milestone','milestone_id':foreign_milestone['id']},
    )
    assert invalid_milestone_task.status_code==400


def test_task_parent_cycle_is_rejected(client):
    headers=auth(client)
    project=create_project(client,headers,'Hierarchy validation')
    project_id=project['id']
    first=client.post(f'/api/v1/projects/{project_id}/tasks',headers=headers,json={'title':'Parent task'}).json()
    second=client.post(f'/api/v1/projects/{project_id}/tasks',headers=headers,json={'title':'Child task','parent_task_id':first['id']}).json()

    response=client.patch(
        f"/api/v1/projects/{project_id}/tasks/{first['id']}",
        headers=headers,
        json={'parent_task_id':second['id']},
    )
    assert response.status_code==409


def test_cycle_update_rejects_null_or_reversed_dates(client):
    headers=auth(client)
    project=create_project(client,headers,'Cycle date validation')
    cycle=client.post(
        f"/api/v1/projects/{project['id']}/cycles",
        headers=headers,
        json={'name':'Valid cycle','start_date':'2026-11-01','end_date':'2026-11-14'},
    ).json()
    null_date=client.patch(
        f"/api/v1/projects/{project['id']}/cycles/{cycle['id']}",
        headers=headers,
        json={'end_date':None},
    )
    assert null_date.status_code==422
    reversed_date=client.patch(
        f"/api/v1/projects/{project['id']}/cycles/{cycle['id']}",
        headers=headers,
        json={'end_date':'2026-10-31'},
    )
    assert reversed_date.status_code==422
