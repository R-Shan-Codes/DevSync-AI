from cryptography.fernet import Fernet

from app.core import config
from app.core.github_security import decrypt_token, encrypt_token


def register(client, email):
    client.post("/api/v1/auth/register", json={"email": email, "display_name": "GitHub Tester", "password": "secure-pass-123"})
    token = client.post("/api/v1/auth/login", data={"username": email, "password": "secure-pass-123"}).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_github_account_status_and_repository_requires_connection(client):
    headers = register(client, "github-user@example.com")
    status = client.get("/api/v1/github/account", headers=headers)
    assert status.status_code == 200
    assert status.json() == {"connected": False}
    repos = client.get("/api/v1/github/repositories", headers=headers)
    assert repos.status_code == 409


def test_github_connect_requires_oauth_configuration(client, monkeypatch):
    monkeypatch.setattr(config.settings, "github_client_id", "")
    monkeypatch.setattr(config.settings, "github_client_secret", "")
    headers = register(client, "github-config@example.com")
    response = client.get("/api/v1/github/connect", headers=headers)
    assert response.status_code == 503


def test_github_connect_returns_signed_authorization_url(client, monkeypatch):
    monkeypatch.setattr(config.settings, "github_client_id", "test-client-id")
    monkeypatch.setattr(config.settings, "github_client_secret", "test-client-secret")
    monkeypatch.setattr(config.settings, "github_token_encryption_key", Fernet.generate_key().decode())
    headers = register(client, "github-oauth@example.com")
    response = client.get("/api/v1/github/connect", headers=headers)
    assert response.status_code == 200
    url = response.json()["authorization_url"]
    assert url.startswith("https://github.com/login/oauth/authorize?")
    assert "client_id=test-client-id" in url
    assert "scope=repo" in url
    assert "state=" in url


def test_github_token_encryption_round_trip(monkeypatch):
    key = Fernet.generate_key().decode()
    monkeypatch.setattr(config.settings, "github_token_encryption_key", key)
    encrypted = encrypt_token("gho_example_token")
    assert encrypted != "gho_example_token"
    assert decrypt_token(encrypted) == "gho_example_token"
