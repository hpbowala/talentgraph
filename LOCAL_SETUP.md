# TalentGraph — Local Setup Guide

Run the full system on your machine: FastAPI backend, React chat frontend, and
the LangGraph agents, with no AWS account required. Chat history is kept in
memory, the knowledge graph is read from the committed `vault/` directory, and
sign-in is switched off — see [Authentication](#6-authentication)
below.

## 1. Prerequisites

| Tool | Purpose | Install |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | Python environments (resolves Python 3.12 itself) | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| Node.js 20+ / npm | Frontend build and dev server | [nodejs.org](https://nodejs.org) or `brew install node` |
| OpenAI API key | LLM inference (extraction + chat agents) | [platform.openai.com](https://platform.openai.com) |

## 2. Install dependencies

```bash
git clone <repo-url>
cd cloud-assignment
make install     # uv sync in backend/ and infrastructure/, npm install in frontend/
```

## 3. Configure the environment

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env` and set:

```bash
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-5-mini   # optional override
VAULT_SOURCE=local        # keep this for local runs
```

The AWS block in the file is only needed for cloud deployment — see the
[Deployment Guide](DEPLOYMENT.md).

## 4. Run it

The generated vault is committed to the repo, so **no ingestion is required
before first run**. Two terminals:

```bash
make serve          # FastAPI backend → http://localhost:8000
make frontend-dev   # Vite dev server → http://localhost:5173
```

Open <http://localhost:5173>. You land on `/`; the button reads **Open the app**
before a user pool exists and **Sign in** once one does. Ask something like
*"Who has Python experience?"*.

> **Use `make frontend-dev`, not `npm run dev`.** The Cognito ids are passed in
> by the Makefile, so a bare `npm run dev` starts an unconfigured app where the
> login form fails with *"Authentication is not configured"*. Worse, if one is
> already running, `make frontend-dev` finds port 5173 taken and quietly moves to
> 5174 — leaving the broken one at the address you have open. If in doubt, check
> the port in the Vite banner.

The dev frontend calls the backend on port 8000 directly (`VITE_API_BASE`
defaults to `http://localhost:8000` in `frontend/src/api.ts`), and CORS for
`localhost:5173` is already configured.

The SPA is routed: `/` landing, `/login` sign-in, `/app` chat. `/app` requires a
session and redirects to `/login` without one, returning you to `/app` after you
sign in. See the routes table in the [README](README.md#routes).

Prefer the terminal? `make chat` starts a CLI chat REPL instead of the web UI.

## 5. Optional workflows

```bash
make ingest    # rebuild the vault from data/sample_cvs (calls OpenAI, cached)
make cvs       # re-render data/cv_sources/*.txt into the data/sample_cvs/ corpus
make test      # pytest unit tests
make lint      # ruff checks (backend + infrastructure)
make format    # ruff autofix + format
```

`make ingest` rewrites the `vault/` directory from scratch (People, Skills,
Technologies, Projects, Domains, Education) so removed entities do not linger.
Pass-through flags are available by running the CLI directly from `backend/`:
`uv run talentgraph-ingest --no-cache --no-merge`.

The same pipeline runs behind the app's **CV library** panel: uploading or
deleting a CV there writes to `data/sample_cvs/` locally (to the S3 bucket in the
cloud) and rebuilds the vault in the background. `make ingest` also caches each
extracted profile under `.cache/profiles/`, which `make upload` ships to the
bucket so the first upload in the cloud only has to extract the new CV.

## 6. Authentication

The app is gated by a Cognito user pool, because the deployed site sits on a
public CloudFront URL. **Once you have deployed once, local runs use that same
real pool** — `make serve` and `make frontend-dev` read the pool and client ids
back from the stack outputs themselves, so `make frontend-dev` shows the real
login screen and `make serve` verifies real access tokens. Nothing to paste, and
no separate "local auth" path that could drift from the deployed one.

```bash
make deploy        # creates the pool (see DEPLOYMENT.md)
make cognito-user  # creates your account
make serve         # now verifies tokens against that pool
make frontend-dev  # now shows the login screen
```

Sign in with the account from `make cognito-user`. The backend needs AWS
credentials for this, since it calls Cognito to validate each token; the browser
talks to Cognito directly and needs none.

Both halves read the same configuration:

- **Backend** — `backend/app/auth.py` reads `COGNITO_USER_POOL_ID`, from the
  environment or `backend/.env`. Set, every route except `/health` requires
  `Authorization: Bearer <access token>` and answers `401` without one.
- **Frontend** — `frontend/src/auth.ts` reads `VITE_COGNITO_USER_POOL_ID` and
  `VITE_COGNITO_CLIENT_ID` at build time.

Precedence: when the stack is deployed, `make serve` and `make frontend-dev`
pass its pool id in as an environment variable and that wins. With no stack, the
value falls back to your shell environment and then to `backend/.env`, where the
key is documented in `.env.example` — useful for pinning a pool from another
account. Run uvicorn directly instead of through `make` and the shell and
`.env` are all that apply.

**Before your first deploy** there is no pool anywhere, so the gate stays open
and the landing page's button reads *Open the app* instead of *Sign in*. That is
what lets a fresh clone run with no AWS account at all. It is the only ungated
configuration, and the deployed stack can never be in it — CDK always sets
`COGNITO_USER_POOL_ID` on the proxy.

## 7. How local mode differs from the cloud

| Concern | Local | Cloud |
| --- | --- | --- |
| Vault | read from `vault/` (`VAULT_SOURCE=local`) | downloaded from S3 at cold start |
| CV corpus | `data/sample_cvs/` on disk | `cvs/` in the S3 data bucket |
| Reindexing | FastAPI background task | async self-invocation of the Lambda proxy |
| Chat history | in-memory, lost on restart (`CONVERSATION_STORE=memory`) | DynamoDB |
| Sign-in | the deployed Cognito pool once you have deployed; open before that | Cognito user pool, token on every request |
| Data on teardown | n/a | bucket, table and pool are `RETAIN` (`RETAIN_DATA=false` opts out) |
| OpenAI key | `backend/.env` | SSM Parameter Store (SecureString) |
| API surface | FastAPI (`app/api/server.py`) on :8000 | AgentCore Runtime + Lambda proxy |

Both paths share the same core logic in `backend/app/service.py`.

## Troubleshooting

- **`make: *** No rule to make target ...`** — run `make` from the repository
  root; every target `cd`s into the right subdirectory itself.
- **401/429 from OpenAI** — check `OPENAI_API_KEY` in `backend/.env` and your
  OpenAI billing/limits.
- **Frontend shows connection errors** — make sure `make serve` is running on
  port 8000; the SPA calls it directly in dev.
- **Every request 401s locally** — the backend is gated but the browser has no
  session. Sign in, or unset `COGNITO_USER_POOL_ID` to turn the gate off.
- **Login fails with "Authentication is not configured"** — the frontend was
  started without the Cognito ids. Stop any stray `npm run dev` (`pkill -f vite`)
  and use `make frontend-dev`.
- **Login fails with a 400 from `cognito-idp.amazonaws.com`** — usually
  `NotAuthorizedException`: wrong password, or the account does not exist in the
  pool the app is pointed at. `prevent_user_existence_errors` deliberately gives
  the same message for both. Check with
  `aws cognito-idp list-users --user-pool-id <id> --query 'Users[].Username'`,
  and create the account with `make cognito-user` if the list is empty.
- **`admin-set-user-password` appears to hang** — a curly quote (`'`) in the
  password instead of a straight `'` leaves the shell waiting for the quote to
  close. Retype it in the terminal rather than pasting from a document.
- **Stale answers after re-ingesting** — the backend caches the graph per
  process; restart `make serve` after `make ingest`.
