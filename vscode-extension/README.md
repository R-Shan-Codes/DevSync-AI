# DevSync VS Code Extension

DevSync connects the editor to the project workflow API.

## Setup

1. Start the DevSync backend and dashboard.
2. Open this repository's `vscode-extension` folder in VS Code.
3. Run `npm install` and `npm run compile`.
4. Press F5 to launch the Extension Development Host.
5. Run **DevSync: Connect Account** from the Command Palette.
6. Run **DevSync: Select Project** and enter the project ID.
7. Open the DevSync activity-bar view and refresh the task list.

## Task actions

Right-click a task in the DevSync **My Tasks** tree:

- **Move Task to Next Stage** offers valid next workflow states. The backend remains authoritative and enforces role permissions.
- **Report Bug for Task** collects a title, reproduction details and severity, then creates a project bug report.

Other commands include task refresh, role/permission inspection, dashboard opening, local Git commit sync and GitHub repository sync.

## Configuration

- `devsync.apiUrl`: backend API base URL (default `http://127.0.0.1:8000/api/v1`).
- `devsync.projectId`: active project ID.
- `devsync.workspaceRoot`: optional backend workspace root mapping used by local Git sync.
- `devsync.role`: display preference; the backend membership remains authoritative.

Authentication tokens are stored using VS Code SecretStorage, not workspace settings.

## Verification

Compile with `npm run compile`. Interactive API actions require a running backend, a valid account, project membership and the corresponding permission.
