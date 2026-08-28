# TalentGraph — Deployment Guide

Deploy the full system to AWS with a single CDK stack. Everything is
reproducible from the CLI — nothing is configured in the AWS console.

## What gets deployed

```text
Browser
   │  sign in (SRP) ──────► Cognito user pool   (no sign-up; one admin-made account)
   ▼
CloudFront ──────────────► S3 frontend bucket   (React SPA, default behavior)
   │  /chat, /conversations*, /cvs*   + Authorization: Bearer <access token>
   ▼
Lambda proxy (Function URL) ──► Cognito GetUser  (validates the token; 401 if not)
   │                        └──► DynamoDB conversations table   (list/get/delete)
   │                        └──► S3 data bucket  (GET /cvs listing + index manifest)
   │  POST /chat, POST/DELETE /cvs (SigV4-signed InvokeAgentRuntime)
   │  ↳ then re-invokes itself asynchronously to run the reindex
   ▼
AgentCore Runtime (arm64 container from backend/)
   ├── reads vault/ from the S3 data bucket at cold start
   ├── reads the OpenAI key from SSM Parameter Store
   ├── writes cvs/, profiles/ and vault/ when a CV is added or removed
   └── writes chat turns to the DynamoDB table
```

**Why CV writes return `202`.** Adding a CV re-extracts the corpus and rewrites
the vault — minutes of work, well past CloudFront's 60s origin timeout. The proxy
stores the file, answers immediately, and drives the rebuild from a second,
asynchronous invocation of itself; the SPA polls `GET /cvs` until the index stamp
in `vault/.index.json` moves. Every runtime instance compares that stamp before
answering a question, so a CV uploaded through one instance is picked up by all
of them.

The Lambda proxy exists because invoking AgentCore requires SigV4-signed
requests, which a browser cannot make. CloudFront serves the SPA and the API
from one domain, so the frontend is built with `VITE_API_BASE=""` (same-origin
requests) and needs no hardcoded endpoint.

**Why authentication lives in the proxy.** The site sits on a public CloudFront
URL, and the proxy is the only route to the data — the runtime accepts nothing
but SigV4-signed calls the proxy makes itself. So one check there covers
everything. Every route except `/health` requires a Cognito access token, which
the proxy validates by calling `GetUser` with it: signature, expiry and
revocation in a single call, with no JWT library and therefore no bundling step
for an otherwise dependency-free Lambda asset. Sign-up is disabled on the pool,
so the account you create by hand is the only way in. The static SPA bundle is
still downloadable by anyone — it contains no data, and every request it makes
is gated.

**SPA routing and CloudFront.** The frontend is a routed app (`/` landing,
`/login`, `/app` chat), which puts two constraints on the distribution. Deep links
must reach `index.html`: S3 with OAC answers 403 for a key like `/app`, and the
stack's `error_responses` rewrites that to `/index.html` with a 200, so a refresh
on any route works. And the app's own paths must not collide with the API's — the
chat screen is at `/app`, not `/chat`, because `/chat`, `/conversations*` and
`/cvs*` are behaviors routed to the Lambda proxy and would never reach the SPA.

The CDK app lives in `infrastructure/` (`app.py`, `stacks/talentgraph_stack.py`,
`proxy/handler.py`).

## 1. Prerequisites (one-time)

```bash
# AWS CLI configured with an IAM user/role that can deploy CloudFormation
aws configure                  # or: aws configure sso
aws sts get-caller-identity    # verify credentials work

# CDK CLI (needs Node, which you already have for the frontend)
npm install -g aws-cdk
cdk --version                  # verify

# Project dependencies (backend, infrastructure, frontend)
make install
```

Also required:

- **Docker running** — the runtime image is built for `linux/arm64` during
  deploy.
- **A region with AgentCore Runtime** — e.g. `us-east-1` or `us-west-2`; use
  the same region in `aws configure` and `backend/.env`.

## 2. Configure `backend/.env`

The AWS block is read by **both** the backend and `cdk deploy`
(`infrastructure/app.py` loads this file), so every resource name is defined
exactly once:

```bash
AWS_REGION=us-east-1
VAULT_BUCKET=...                # data bucket: cvs/ + vault/ prefixes
FRONTEND_BUCKET=...             # SPA hosting bucket
CONVERSATIONS_TABLE=talentgraph-conversations
OPENAI_KEY_PARAM=/talentgraph/openai-api-key
RETAIN_DATA=true                # keep data + accounts on teardown (see §5)
```

> **Renaming a bucket or the table creates a new, empty one.** Those names are
> replacement-forcing properties, so changing one after a deploy gives you a fresh
> resource; `RETAIN_DATA=true` means the old one is left in place rather than
> deleted, but the app will no longer be pointed at it.

> **S3 bucket names are globally unique across all AWS accounts.** If a name is
> taken anywhere in the world, the deploy fails with `BucketAlreadyExists` —
> include something unique to you (e.g. your account id). If a name is left
> unset, the stack falls back to a deterministic
> `talentgraph-data-<account-id>` style name.

Keep `VAULT_SOURCE=local` in your `.env`: the stack sets `VAULT_SOURCE=s3` and
`CONVERSATION_STORE=dynamodb` as environment variables inside the runtime.

## 3. Deploy

All commands run from the repository root:

```bash
make openai-key    # once: copy OPENAI_API_KEY from backend/.env → SSM SecureString
make bootstrap     # once per account/region: cdk bootstrap
make deploy        # the actual deployment (details below)
make cognito-user  # once: create the sign-in account in the pool just deployed
make deploy        # again, so the SPA is built with the pool ids
make upload        # push sample CVs + committed vault to the data bucket
make outputs       # print SiteUrl, ApiFunctionUrl, AgentRuntimeArn, pool ids, names
```

**Why `make deploy` twice.** The SPA needs the user-pool and client ids at build
time, and the pool does not exist until the first deploy creates it. `make
frontend-build` reads them back out of the stack outputs, so the second pass
picks them up automatically — there is nothing to paste. Every later deploy is
single-pass, because the ids are then stable. Between the two passes the site
loads but cannot sign in, which is expected.

The first two targets are thin wrappers; their raw equivalents, if you prefer
to run them by hand:

```bash
# make openai-key
aws ssm put-parameter \
  --name /talentgraph/openai-api-key \
  --type SecureString --overwrite \
  --value "sk-..."

# make bootstrap
cdk bootstrap aws://<ACCOUNT_ID>/<REGION>   # run from infrastructure/
```

`make deploy` does three things: builds the SPA with `VITE_API_BASE=""` and the
Cognito ids from the stack outputs, builds and pushes the arm64 container image,
then `cdk deploy` creates/updates every resource — including uploading
`frontend/dist` to S3 and invalidating CloudFront. The first run takes several
minutes (CloudFront distribution creation dominates).

Run `make upload` **before the first chat**: the runtime downloads `vault/`
from S3 at cold start and fails if the prefix is empty.

### The sign-in account

`make cognito-user` prompts for a username and password and runs two calls, so
neither value is written to a file, a template, or your shell history:

```bash
aws cognito-idp admin-create-user     --user-pool-id <UserPoolId> \
  --username <you> --message-action SUPPRESS     # SUPPRESS = send no invite mail
aws cognito-idp admin-set-user-password --user-pool-id <UserPoolId> \
  --username <you> --password '<password>' --permanent
```

`--permanent` is the important flag: without it Cognito leaves the account in
`FORCE_CHANGE_PASSWORD`, and the app's login form has no screen for that
challenge. The password policy on the pool requires 12+ characters with upper,
lower and a digit.

Adding more people later is the same command again. There are no roles: any
account in the pool can read the graph and manage the CV library.

## 4. Verify

Open the `SiteUrl` output in a browser. You land on the marketing page; **Sign
in** goes to `/login`, and the account is the one from `make cognito-user`. After
signing in you are on `/app`. Then ask a question.

Worth checking once, since it exercises the CloudFront rewrite: open
`<SiteUrl>/app` directly in a new tab. Signed out it should redirect you to
`/login`, not 403 or show a blank page. The first request is slow
(container boot + vault download); if it times out through CloudFront once,
retry — the warm runtime answers quickly.

The gate is easy to check from the shell — no token, no data:

```bash
curl -si "$(make -s outputs | grep -o 'https://[a-z0-9]*\.cloudfront\.net')/conversations" | head -1
# HTTP/2 401
```

To test the runtime without the frontend:

```bash
aws bedrock-agentcore invoke-agent-runtime \
  --agent-runtime-arn <AgentRuntimeArn output> \
  --runtime-session-id test-session-0000000000000000000000000 \
  --payload '{"message": "Who knows React?"}' out.json && cat out.json
```

Logs land in CloudWatch under `/aws/bedrock-agentcore/runtimes/...` (runtime)
and `/aws/lambda/TalentGraphStack-ApiProxy...` (proxy).

## 5. Redeploying and teardown

| Change | Command |
| --- | --- |
| Backend or frontend code | `make deploy` |
| CVs / vault content | `make ingest` then `make upload` (start a fresh chat session — each container caches the vault) |
| OpenAI key rotation | `make openai-key` (new runtimes pick it up at next cold start) |
| Add or reset a sign-in account | `make cognito-user` (no redeploy needed) |
| Remove everything | `make destroy` — but see **What survives a teardown** below |

### Deploys never recreate your data

CloudFormation updates resources in place, so `make deploy` does not touch the
CV corpus, the chat history or your Cognito accounts, however many times you run
it. The risk is not deploying, it is *removing*: a `cdk destroy`, or a property
change that forces CloudFormation to replace a resource rather than update it.

Both are covered. The data bucket, the DynamoDB table and the user pool are
created with `RemovalPolicy.RETAIN`, which sets both `DeletionPolicy` and
`UpdateReplacePolicy` to `Retain` — so neither a teardown nor a replacement can
delete them. The frontend bucket is deliberately excluded: it holds the compiled
SPA, which every deploy rewrites from source.

The properties that would otherwise force a replacement are all names in
`backend/.env` — `VAULT_BUCKET`, `CONVERSATIONS_TABLE` — plus the pool's
sign-in aliases. Changing any of those still gives you a *new*, empty resource;
retention means the old one is left intact beside it rather than deleted.

### What survives a teardown

`make destroy` removes the CloudFront distribution, the Lambda proxy, the
AgentCore runtime and the frontend bucket, and **leaves behind** the data bucket,
the conversations table and the user pool, with their contents.

That is the point, but it has a consequence: a later `make deploy` using the same
names fails with `BucketAlreadyExists` or `Resource already exists`, because CDK
tries to create resources that are still there. Either delete them by hand first,
or set `RETAIN_DATA=false` in `backend/.env` and redeploy *before* destroying, so
the teardown takes everything with it.

## Troubleshooting

- **`BucketAlreadyExists`** — pick a more unique bucket name in `backend/.env`
  and `make deploy` again.
- **`Resource ... already exists` for the DynamoDB table** — a table with that
  name exists outside the stack: either the backend auto-created one by running
  in dynamodb mode before the first deploy, or a previous `make destroy` retained
  it (see **What survives a teardown**). Delete it
  (`aws dynamodb delete-table --table-name <name>`) or choose another name.
- **504 through the site on first message** — cold-start exceeded CloudFront's
  60 s origin timeout; retry, or hit the `ApiFunctionUrl` directly (120 s).
- **Docker errors during deploy** — Docker Desktop must be running; the image
  targets `linux/arm64`.
- **`No vault notes found under s3://...`** in runtime logs — `make upload` was
  skipped or targeted a different bucket than the stack's `VAULT_BUCKET`.
- **Sign-in screen says "Authentication is not configured"** — the SPA was built
  before the pool existed. Run `make deploy` again; `make outputs` should show
  `UserPoolId` and `UserPoolClientId`.
- **Every request comes back 401 right after signing in** — the bundle carries a
  different pool than the proxy checks against, which happens if the stack was
  destroyed and recreated between builds. `make deploy` rebuilds against the
  current pool.
- **`NotAuthorizedException` from `make cognito-user`** — the password does not
  meet the pool policy (12+ characters, upper, lower, digit), or the username
  already exists; `admin-set-user-password` alone resets an existing account.
- **Login rejects a correct password with "User does not exist"** — the pool
  returns one generic message for both cases on purpose
  (`prevent_user_existence_errors`), so check the username too.
