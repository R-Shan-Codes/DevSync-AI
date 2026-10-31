# DevSync AI Architecture

## System shape
A modular FastAPI monolith serves the React + TypeScript dashboard and TypeScript VS Code extension. REST APIs handle request/response operations; authenticated project-scoped WebSockets deliver activity notifications and refresh signals. SQLite is the initial persistence target behind SQLAlchemy.

Git remains the source of truth for version control and merges. DevSync coordinates people, tasks, reviews, QA evidence, planning and AI context around Git rather than replacing Git.

## Backend domains
- Authentication, project membership and permission enforcement.
- Task lifecycle, assignment, priority, due dates, comments and parent-child hierarchy.
- Project cycles/sprints and milestones/roadmap records.
- Activity timeline, Git events, commit/task links and GitHub webhooks.
- Code review, test evidence, bug tracking, dependency analysis and delivery pipeline.
- Gemini-backed role assistance, recommendations, GitHub PR review and failed-CI diagnosis.
- Project memory, contribution evidence, handovers and conflict intelligence.

## Planning data model
- A project owns many cycles and milestones.
- A cycle has a name, goal, start/end dates and planned/active/completed status.
- A milestone has a name, description, optional target date and planned/in-progress/completed status.
- A task may be linked to one cycle and one milestone.
- A task may have one parent task; the API validates same-project references and rejects hierarchy cycles.
- Cycle and milestone progress is derived from linked task statuses, not stored as a manually maintained percentage.

## Clients
The dashboard provides overview, tasks, project planning, team, activity, Git/GitHub, AI assistance and development intelligence. The Planning workspace creates cycles and milestones, changes their status, assigns tasks to planning entities and displays parent-child task structure.

The VS Code extension connects authenticated users to projects, displays tasks and sends bounded workspace/file/Git metadata. It does not upload source file contents through its telemetry path.

## Security and data boundaries
- Roles and permissions belong to project membership.
- Project-scoped endpoints validate membership and permissions server-side.
- Planning writes and task relationship edits require project edit permission.
- Cross-project task/cycle/milestone references are rejected.
- AI findings and suggested assignments remain advisory; humans confirm consequential changes.
- GitHub webhook deliveries are signature-verified and deduplicated; provider credentials remain server-side and encrypted at rest.

## Realtime behavior
Project WebSockets broadcast task, planning and integration events. The dashboard refreshes persisted data when events arrive. The VS Code extension batches metadata events and retries transient failures using a bounded queue.

## Production constraints and next hardening
SQLite remains the initial database; production database strategy and backup/restore are not finalized. SQLAlchemy metadata creation and additive SQLite compatibility migrations are currently used; Alembic migrations are required before production. Live GitHub OAuth, public webhook delivery and Gemini calls require deployment verification. Additional production work includes secret rotation, token lifecycle/revocation, explicit CORS policy, rate limits, structured audit trails and observability.
