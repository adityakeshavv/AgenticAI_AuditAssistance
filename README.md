# Agentic AI-Powered Audit Assistant

An enterprise audit copilot that combines authenticated user workspaces, database connectors, agent orchestration, evidence retrieval, risk scoring, traceability, and executive-ready responses.

## What the system does

- Lets users sign up and sign in with local credentials or Google sign-in
- Supports role-aware access control with `admin` and `user`
- Lets users create workspaces and scope queries to selected data sources
- Connects to PostgreSQL through a generic connector layer
- Runs audit queries through an agentic workflow
- Retrieves structured evidence and supporting documents
- Generates findings, recommendations, risk ratings, and response quality evaluation
- Captures traceability and Langfuse spans for observability
- Provides a React dashboard, audit workspace, chat assistant, and source management UI

## Current capabilities

### Authentication and RBAC

- Local login and signup
- Google OAuth login
- Secure password hashing
- Session tokens
- Admin allowlist based on email
- Route-level access checks for workspaces and database sources

### Workspace and source management

- Create and manage audit workspaces
- Select one or more saved database sources per workspace
- Choose an active source for query execution
- Test database connections before saving
- List schemas and tables from connected sources

### Connector framework

- Generic database connector service
- PostgreSQL support implemented first
- Pluggable structure for future sources such as MySQL, SQL Server, and cloud databases
- Agents consume data through the connector layer rather than directly binding to a database type

### Audit workflow

- Intent extraction
- Investigation planning
- Agent orchestration
- Transaction retrieval
- Vendor retrieval
- Document retrieval
- Evidence aggregation
- Finding generation
- Recommendation generation
- Risk scoring
- Validation
- Response composition
- Traceability capture

### Document and evidence intelligence

- Document metadata storage in PostgreSQL
- Document evidence extraction from physical files
- Page-aware citation support
- Source navigation payloads
- Evidence snippets and supporting document references

### Observability

- Langfuse tracing for query lifecycle visibility
- Execution metadata for agent steps
- LLM call metadata where applicable
- Response evaluation for grounding and faithfulness

### Frontend

- Authentication screen
- Executive dashboard
- Floating audit assistant
- Workspace management
- Source connection management
- Audit response view
- Traceability and evidence views
- Citation navigation and document review

## High-level architecture

```text
User
  -> React UI
  -> FastAPI backend
  -> Auth / RBAC
  -> Workspace + Source Selection
  -> Connector Layer
  -> Agent Orchestrator
  -> Retrieval / Evidence / Finding / Risk / Validation
  -> Response Composer
  -> Traceability + Langfuse
  -> Final Audit Response
```

## Tech stack

- Frontend: React, TypeScript, Vite
- Backend: FastAPI, Python
- Database: PostgreSQL
- ORM: SQLAlchemy 2.0
- Validation: Pydantic v2
- AI / agents: OpenAI-compatible flows, Gemini ADK workflow support
- Observability: Langfuse

## Repository layout

- `backend/` - FastAPI app, services, routers, schemas, auth, workspaces, connectors
- `frontend/` - React dashboard, audit assistant, source management, admin UI
- `agents/` - agent entry points and routing logic
- `database/` - schema, loaders, validation, metadata scripts
- `rag/` - document ingestion, chunking, embeddings, vector store foundation
- `docs/` - project notes and planning material

## Local setup

### Backend

1. Create and activate a virtual environment
2. Install backend requirements
3. Configure `backend/.env`
4. Start the FastAPI app

### Frontend

1. Install frontend dependencies
2. Set `VITE_API_BASE_URL`
3. Start the Vite dev server

## Important environment variables

Backend:

- `DATABASE_URL`
- `AUTH_TOKEN_SECRET`
- `OPENAI_API_KEY`
- `OPENAI_MODEL`
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `GOOGLE_REDIRECT_URI`
- `FRONTEND_AUTH_REDIRECT_URI`
- `ADMIN_EMAILS`
- `LANGFUSE_ENABLED`
- `LANGFUSE_PUBLIC_KEY`
- `LANGFUSE_SECRET_KEY`
- `LANGFUSE_HOST`
- `GEMINI_MODEL`
- `GOOGLE_CLOUD_PROJECT_ID`
- `GOOGLE_CLOUD_LOCATION`

Frontend:

- `VITE_API_BASE_URL`

## Typical user flow

1. Sign in
2. Select or create a workspace
3. Choose a saved database source
4. Ask an audit question
5. Router/planner selects the best flow
6. Agents retrieve structured and document evidence
7. The system scores risk, generates findings, and validates support
8. The response is rendered with citations, traceability, and evaluation

## Status

The platform now has a working foundation for:

- authenticated audit access
- workspace-scoped source selection
- generic database connectivity
- agentic audit workflows
- evidence-backed responses
- executive dashboard and traceability UI

## Future direction

- broader multi-agent orchestration
- deeper semantic document retrieval
- richer admin controls
- additional database connectors
- tighter memory and conversation context
- more advanced source-level traceability

