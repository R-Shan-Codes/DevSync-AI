# Live GitHub and Gemini integration runbook

This runbook describes the external configuration required to exercise DevSync's GitHub and AI integrations. Automated tests use deterministic local fixtures; they do not prove that credentials, public webhook delivery, GitHub repository permissions or Gemini availability are configured in a deployment.

## Required backend environment

Configure these values in the backend environment, never in frontend or VS Code source:

- `SECRET_KEY`: long random application signing secret.
- `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`: GitHub OAuth App credentials.
- `GITHUB_CALLBACK_URL`: must exactly match the OAuth App callback URL, for example `https://api.example.com/api/v1/github/callback`.
- `GITHUB_TOKEN_ENCRYPTION_KEY`: Fernet key used to encrypt GitHub OAuth tokens at rest. Generate one with `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`. Keep it stable; changing it makes previously stored tokens undecryptable.
- `GITHUB_WEBHOOK_SECRET`: long random secret shared with the GitHub repository webhook.
- `GEMINI_API_KEY`: Google AI Studio / Gemini API key.
- `GEMINI_MODEL`: model name available to the key; default is `gemini-2.5-flash`.
- `FRONTEND_URL` and `CORS_ORIGINS`: deployed dashboard origin(s).

The GitHub OAuth flow requests `repo read:user` so the connected user can list and read repositories they can access. Use a dedicated GitHub integration account with the minimum repository access needed. Do not paste credentials into issues, PRs, screenshots or chat logs.

## GitHub OAuth and repository linking

1. Create a GitHub OAuth App and set its callback URL to the exact deployed `GITHUB_CALLBACK_URL`.
2. Configure the client ID, client secret and Fernet encryption key on the backend.
3. Sign in to the DevSync dashboard and connect GitHub.
4. Link the intended repository to the project. The connected account must have access to that repository.
5. Confirm the project repository is displayed as the expected `owner/repository`.

If connection fails, check the callback URL, app credentials, backend clock, application `SECRET_KEY`, encryption key format and whether the connected account can access the repository.

## Webhook delivery

The GitHub repository webhook must target:

`https://YOUR_API_HOST/api/v1/github/webhooks`

Configure:
- Content type: `application/json`
- Secret: exactly the backend `GITHUB_WEBHOOK_SECRET`
- Events: Push, Pull requests, Check runs and Check suites
- Active: enabled

The endpoint requires HTTPS in a deployed environment. GitHub must be able to reach the public API host; localhost and private LAN URLs are not reachable by GitHub. The receiver verifies `X-Hub-Signature-256`, caps request bodies at 2 MB, records delivery IDs for idempotency, associates repositories by exact owner/repository name, and ignores unlinked repositories or unsupported event types.

In GitHub's webhook **Recent Deliveries**, inspect the response code and response body:
- `200`: accepted; `outcome=processed` means a linked repository event was handled; `outcome=ignored` means no matching project or unsupported event.
- `401`: signature mismatch; compare the webhook secret and backend environment.
- `413`: payload exceeded the 2 MB receiver limit.
- `503`: webhook secret is not configured on the backend.
- `5xx`: inspect backend logs and retry the delivery after correcting the cause.

Push deliveries persist commit metadata and project activity. Pull-request and CI check deliveries persist activity records. Duplicate delivery IDs are acknowledged without replaying writes; duplicate commit hashes arriving in separate push deliveries are also idempotent.

## Gemini-assisted pull-request review and CI diagnosis

1. Set `GEMINI_API_KEY` and a supported `GEMINI_MODEL` on the backend.
2. Connect a GitHub account that can read the linked repository and, for CI diagnosis, its Actions runs and job logs.
3. In the dashboard, open the GitHub tab.
4. Request a review using a pull-request number, or diagnose failed checks using the full commit SHA.
5. Review the persisted analysis and explicitly link it to a task if it is relevant.

The PR diff download is capped at 2 MB and the text supplied to Gemini at 60,000 characters. CI log downloads are streamed with a 10 MB compressed-download limit; ZIP extraction is bounded to 20 log files and 45,000 characters. Common GitHub, Google, AWS, bearer, JWT, Slack, npm and key/value credential patterns are redacted before evidence is sent to Gemini. The Gemini key is sent in the request header, not the URL.

These protections reduce accidental disclosure but cannot guarantee detection of every secret format. Do not submit evidence containing credentials, personal data or confidential customer information unless your organization's policy explicitly permits that transfer. Verify AI findings against source and test evidence. AI analysis never comments on or approves GitHub PRs, edits code, changes task status or merges code.

## What automated CI verifies

The backend test suite covers webhook signature validation, delivery idempotency, duplicate commit idempotency, exact repository matching, push/PR/check event persistence, AI output normalization, credential redaction, bounded log ZIP extraction/downloads, access control and task-link persistence. Frontend CI type-checks and builds the dashboard. Extension CI compiles the VS Code extension.

CI does not exercise a real GitHub OAuth exchange, public webhook delivery, a live private repository, GitHub Actions log permissions or a live Gemini request. Those remain deployment-dependent acceptance checks and should be performed only after the complete-project test phase is announced.


## Dashboard integration diagnostics

The GitHub tab includes **Run live checks**. It calls `POST /api/v1/github/projects/{project_id}/integration-check` and reports:
- Whether GitHub OAuth client credentials and the token encryption key are configured.
- Whether the signed-in user's stored GitHub token can authenticate to GitHub.
- Whether that account can access the project's exact linked repository.
- Whether the configured Gemini model can return a valid structured response (a small connectivity-only request; no source code or logs are sent).
- Whether the webhook secret is configured.

The endpoint does not persist diagnostics, return secrets, or change project state. The webhook item remains a warning even when configured because an outbound API check cannot prove that GitHub can reach the deployment's inbound webhook URL. Confirm that separately by sending a test delivery from GitHub and inspecting **Recent Deliveries**.
