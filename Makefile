.PHONY: install lint format test eval ingest serve chat cvs frontend-dev frontend-build \
	bootstrap openai-key deploy cognito-user upload outputs destroy

STACK := TalentGraphStack
# Resolved lazily (recursive =) so aws is only called by targets that use it.
DATA_BUCKET = $(shell aws cloudformation describe-stacks --stack-name $(STACK) \
	--query "Stacks[0].Outputs[?OutputKey=='DataBucketName'].OutputValue" --output text)
# Cognito ids come from the deployed stack when there is one, otherwise from
# backend/.env — which is what lets local development run against a pool created
# by hand, before the stack has ever been deployed.
# filter-out None: that is what the CLI prints when the stack exists but has no
# such output yet, i.e. between the two passes of a clean-slate deploy.
ENV_FILE := backend/.env
env_value = $(strip $(shell sed -n 's/^[[:space:]]*$(1)=//p' $(ENV_FILE) 2>/dev/null | tail -1))

STACK_USER_POOL_ID = $(filter-out None,$(shell aws cloudformation describe-stacks --stack-name $(STACK) \
	--query "Stacks[0].Outputs[?OutputKey=='UserPoolId'].OutputValue" --output text 2>/dev/null))
STACK_USER_POOL_CLIENT_ID = $(filter-out None,$(shell aws cloudformation describe-stacks --stack-name $(STACK) \
	--query "Stacks[0].Outputs[?OutputKey=='UserPoolClientId'].OutputValue" --output text 2>/dev/null))

USER_POOL_ID = $(or $(STACK_USER_POOL_ID),$(call env_value,COGNITO_USER_POOL_ID))
USER_POOL_CLIENT_ID = $(or $(STACK_USER_POOL_CLIENT_ID),$(call env_value,COGNITO_CLIENT_ID))

# Passed to local runs only when the stack is deployed, so an empty value never
# shadows a COGNITO_USER_POOL_ID set in backend/.env or the shell.
COGNITO_ENV = $(if $(USER_POOL_ID),COGNITO_USER_POOL_ID=$(USER_POOL_ID),)
VITE_COGNITO_ENV = $(if $(USER_POOL_ID),VITE_COGNITO_USER_POOL_ID=$(USER_POOL_ID) \
	VITE_COGNITO_CLIENT_ID=$(USER_POOL_CLIENT_ID),)

install:
	cd backend && uv sync
	cd infrastructure && uv sync
	cd frontend && npm install

lint:
	cd backend && uv run ruff check app && uv run ruff format --check app
	cd infrastructure && uv run ruff check .

format:
	cd backend && uv run ruff check --fix app && uv run ruff format app
	cd infrastructure && uv run ruff format .

test:
	cd backend && uv run pytest

cvs:
	uv run scripts/generate_cv_pdfs.py

ingest:
	cd backend && uv run talentgraph-ingest

# Uses the deployed user pool when there is one, so local runs exercise the real
# login rather than an ungated shortcut.
serve:
	cd backend && $(COGNITO_ENV) uv run uvicorn app.api.server:app --reload --port 8000

chat:
	cd backend && uv run talentgraph-chat

# Evaluation set (tests/eval/queries.yaml). EVAL_ARGS="--url https://..." to
# score a deployed instance, or "--markdown ../EVALUATION.md" to write a report.
eval:
	cd backend && uv run python ../scripts/run_eval.py $(EVAL_ARGS)

frontend-dev:
	cd frontend && $(VITE_COGNITO_ENV) npm run dev

# SPA build for CloudFront: empty VITE_API_BASE = same-origin /chat requests.
# The Cognito ids come from the deployed stack, so a clean-slate install needs two
# passes: the first creates the pool, the second builds a SPA that can see it.
frontend-build:
	cd frontend && VITE_API_BASE="" $(VITE_COGNITO_ENV) npm run build

# ---- Deployment (in order: bootstrap once, openai-key once, deploy, upload) ----

bootstrap:
	cd infrastructure && uv run cdk bootstrap

# Copies OPENAI_API_KEY from backend/.env into SSM for the AgentCore runtime.
openai-key:
	aws ssm put-parameter --name /talentgraph/openai-api-key --type SecureString --overwrite \
		--value "$$(grep '^OPENAI_API_KEY=' backend/.env | cut -d '=' -f2-)"

deploy: frontend-build
	cd infrastructure && uv run cdk deploy

# One-off: create the operator account in the pool the stack just made. Prompts,
# so neither the username nor the password lands in a file or shell history.
# --permanent is what skips Cognito's force-change-password challenge.
cognito-user:
	@read -p "Username: " u; \
	read -s -p "Password: " p; echo; \
	aws cognito-idp admin-create-user --user-pool-id $(USER_POOL_ID) \
		--username "$$u" --message-action SUPPRESS > /dev/null && \
	aws cognito-idp admin-set-user-password --user-pool-id $(USER_POOL_ID) \
		--username "$$u" --password "$$p" --permanent && \
	echo "Created $$u — rerun 'make deploy' so the SPA picks up the pool ids."

# Push sample CVs + committed vault to the data bucket created by the stack.
upload:
	cd backend && VAULT_BUCKET=$(DATA_BUCKET) uv run python -c \
		"from pathlib import Path; from app.ingest.s3_sync import upload_cvs_and_vault; \
		upload_cvs_and_vault(Path('../data/sample_cvs'), Path('../vault'))"

outputs:
	aws cloudformation describe-stacks --stack-name $(STACK) \
		--query "Stacks[0].Outputs" --output table

destroy:
	cd infrastructure && uv run cdk destroy
