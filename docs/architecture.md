# DevSync AI Architecture

A modular FastAPI monolith serves the React dashboard and VS Code extension. REST handles request/response operations; authenticated project-scoped WebSockets are a planned next milestone. SQLite is the initial database behind SQLAlchemy.

Git remains the source of truth for version control and merges. DevSync coordinates developers, tasks, reviews, test outcomes, activity and AI context around Git.

Project roles are membership attributes, not global user attributes. Project routes enforce membership checks. Only administrators manage membership; server-side role checks guard review, testing and merge workflow transitions. AI provider credentials will remain server-side.

The initial development database uses SQLAlchemy metadata table creation for rapid local iteration. Before production, introduce Alembic migrations, stronger deployment validation, refresh/revocation strategy and explicit CORS origins.
