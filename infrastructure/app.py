"""CDK entrypoint: synthesizes the single TalentGraph stack.

Resource names come from backend/.env so the backend and the infrastructure
always agree.
"""

import os
from pathlib import Path

import aws_cdk as cdk

from stacks.talentgraph_stack import TalentGraphStack

REPO_ROOT = Path(__file__).resolve().parents[1]


def load_backend_env() -> None:
    """Read backend/.env into the environment without overriding shell values."""
    env_file = REPO_ROOT / "backend" / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.split("#", 1)[0].strip())


load_backend_env()

app = cdk.App()

TalentGraphStack(
    app,
    "TalentGraphStack",
    env=cdk.Environment(
        account=os.getenv("CDK_DEFAULT_ACCOUNT"),
        region=os.getenv("CDK_DEFAULT_REGION") or os.getenv("AWS_REGION"),
    ),
)

app.synth()
