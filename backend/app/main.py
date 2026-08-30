"""AWS Bedrock AgentCore Runtime entrypoint.

Serves POST /invocations and GET /ping on port 8080 per the AgentCore service
contract. In the cloud the OpenAI key is fetched from SSM Parameter Store and the
vault is downloaded from S3 at cold start (VAULT_SOURCE=s3).
"""

import base64
import binascii
import os

from bedrock_agentcore import BedrockAgentCoreApp

from app.cv_store import CVStoreError
from app.service import (
    add_cv,
    delete_conversation,
    delete_cv,
    get_conversation,
    graph_snapshot,
    handle_chat,
    list_conversations,
    list_cvs,
    reindex_library,
)

app = BedrockAgentCoreApp()


def _load_openai_key_from_ssm() -> None:
    param_name = os.getenv("OPENAI_KEY_PARAM")
    if not param_name or os.getenv("OPENAI_API_KEY"):
        return
    import boto3  # noqa: PLC0415 — only needed in cloud mode

    ssm = boto3.client("ssm")
    value = ssm.get_parameter(Name=param_name, WithDecryption=True)["Parameter"]["Value"]
    os.environ["OPENAI_API_KEY"] = value


_load_openai_key_from_ssm()


@app.entrypoint
def invoke(payload: dict, context=None) -> dict:
    """AgentCore exposes a single route, so thread operations are multiplexed
    through an optional 'action' field ('chat' when omitted)."""
    action = payload.get("action", "chat")
    conversation_id = payload.get("conversation_id")

    if action == "list_conversations":
        return {"conversations": [c.model_dump() for c in list_conversations()]}
    if action == "get_conversation":
        if not conversation_id:
            return {"error": "Request payload must include a 'conversation_id' field."}
        detail = get_conversation(conversation_id)
        if detail is None:
            return {"error": "Unknown conversation_id."}
        return detail.model_dump()
    if action == "delete_conversation":
        if not conversation_id:
            return {"error": "Request payload must include a 'conversation_id' field."}
        delete_conversation(conversation_id)
        return {"deleted": conversation_id}
    if action == "graph":
        return graph_snapshot().model_dump()
    if action in {"list_cvs", "add_cv", "delete_cv", "reindex"}:
        return _cv_action(action, payload)
    if action != "chat":
        return {"error": f"Unknown action '{action}'."}

    message = payload.get("message", "")
    if not message:
        return {"error": "Request payload must include a 'message' field."}
    response = handle_chat(message, conversation_id)
    return response.model_dump()


def _cv_action(action: str, payload: dict) -> dict:
    """CV library management: list, upload (base64 body), delete and reindex.

    Storing and deleting are quick; "reindex" re-extracts the corpus, rewrites
    the vault in S3 and reloads the graph, which takes minutes — the proxy
    invokes it asynchronously.
    """
    try:
        if action == "list_cvs":
            return list_cvs().model_dump()
        if action == "reindex":
            return reindex_library().model_dump()
        filename = payload.get("filename")
        if not filename:
            return {"error": "Request payload must include a 'filename' field."}
        if action == "delete_cv":
            return delete_cv(filename).model_dump()
        try:
            content = base64.b64decode(payload.get("content_base64", ""), validate=True)
        except (binascii.Error, ValueError):
            return {"error": "content_base64 is not valid base64."}
        return add_cv(filename, content).model_dump()
    except CVStoreError as err:
        return {"error": str(err)}


if __name__ == "__main__":
    app.run()
