def auth(client,email='dev@example.com'):
    client.post('/api/v1/auth/register',json={'email':email,'display_name':'Dev','password':'secure-pass-123'})
    token=client.post('/api/v1/auth/login',data={'username':email,'password':'secure-pass-123'}).json()['access_token']
    return {'Authorization':f'Bearer {token}'}



def test_task_priority_due_date_and_comments(client):
    headers = auth(client)
    project = client.post('/api/v1/projects', headers=headers, json={'name': 'Task metadata'}).json()
    project_id = project['id']
    created = client.post(
        f'/api/v1/projects/{project_id}/tasks',
        headers=headers,
        json={'title': 'Ship task details', 'priority': 'urgent', 'due_date': '2026-11-15'},
    )
    assert created.status_code == 201
    task = created.json()
    assert task['priority'] == 'urgent'
    assert task['due_date'] == '2026-11-15'

    updated = client.patch(
        f"/api/v1/projects/{project_id}/tasks/{task['id']}",
        headers=headers,
        json={'priority': 'high', 'due_date': None},
    )
    assert updated.status_code == 200
    assert updated.json()['priority'] == 'high'
    assert updated.json()['due_date'] is None

    comment = client.post(
        f"/api/v1/projects/{project_id}/tasks/{task['id']}/comments",
        headers=headers,
        json={'body': 'Please verify the acceptance criteria.'},
    )
    assert comment.status_code == 201
    assert comment.json()['body'] == 'Please verify the acceptance criteria.'
    listed = client.get(
        f"/api/v1/projects/{project_id}/tasks/{task['id']}/comments",
        headers=headers,
    )
    assert listed.status_code == 200
    assert [item['id'] for item in listed.json()] == [comment.json()['id']]


def test_task_comment_and_metadata_project_isolation(client):
    owner_headers = auth(client, 'owner@example.com')
    other_headers = auth(client, 'other@example.com')
    project = client.post('/api/v1/projects', headers=owner_headers, json={'name': 'Private task'}).json()
    task = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=owner_headers,
        json={'title': 'Private discussion'},
    ).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/tasks/{task['id']}/comments",
        headers=other_headers,
        json={'body': 'Should not be visible'},
    )
    assert response.status_code == 404


def test_task_priority_validation(client):
    headers = auth(client)
    project = client.post('/api/v1/projects', headers=headers, json={'name': 'Priority validation'}).json()
    response = client.post(
        f"/api/v1/projects/{project['id']}/tasks",
        headers=headers,
        json={'title': 'Invalid priority', 'priority': 'critical'},
    )
    assert response.status_code == 422
