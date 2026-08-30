"""Browser-facing API proxy (Lambda Function URL behind CloudFront).

AgentCore needs SigV4-signed requests, which the SPA cannot make:

    POST   /chat                      -> bedrock-agentcore InvokeAgentRuntime
    GET    /conversations             -> DynamoDB scan (summaries, newest first)
    GET    /conversations/{id}        -> DynamoDB get_item
    DELETE /conversations/{id}        -> DynamoDB delete_item
    GET    /graph                     -> InvokeAgentRuntime (action: graph)
    GET    /cvs                       -> S3 (cvs/ listing + vault/.index.json)
    POST   /cvs                       -> InvokeAgentRuntime (action: add_cv) + async reindex
    DELETE /cvs/{filename}            -> InvokeAgentRuntime (action: delete_cv) + async reindex

Reads go straight to DynamoDB and S3 so browsing history or polling the CV
listing needs no chat turn. A rebuild takes minutes, so CV writes return 202 and
this function re-invokes itself asynchronously to drive the reindex.

Every route requires a Cognito access token — this is the only public entry
point to the data.
"""

import base64
import binascii
import json
import os
import urllib.parse
import uuid

import boto3
from botocore.exceptions import ClientError

AGENT_RUNTIME_ARN = os.environ["AGENT_RUNTIME_ARN"]
TABLE_NAME = os.environ["CONVERSATIONS_TABLE"]
DATA_BUCKET = os.environ["DATA_BUCKET"]
# Set by the stack whenever a user pool exists; empty disables the gate, which
# only happens if the proxy is deployed by hand without one.
USER_POOL_ID = os.environ.get("COGNITO_USER_POOL_ID", "")

_agentcore = boto3.client("bedrock-agentcore")
_lambda = boto3.client("lambda")
_s3 = boto3.client("s3")
_cognito = boto3.client("cognito-idp")
_table = boto3.resource("dynamodb").Table(TABLE_NAME)

# Kept in step with backend/app/cv_store.py.
SUPPORTED_SUFFIXES = (".pdf", ".txt", ".md")
MAX_CV_BYTES = 4 * 1024 * 1024
CV_PREFIX = "cvs/"
MANIFEST_KEY = "vault/.index.json"
REINDEX_TASK = "reindex"


def _response(status: int, body) -> dict:
    return {
        "statusCode": status,
        "headers": {"content-type": "application/json"},
        "body": json.dumps(body, default=str),
    }


def _invoke(payload: dict, session_id: str) -> dict:
    result = _agentcore.invoke_agent_runtime(
        agentRuntimeArn=AGENT_RUNTIME_ARN,
        # session ids must be >= 33 chars; conv-<uuid4> is 41
        runtimeSessionId=session_id.ljust(33, "0"),
        payload=json.dumps(payload),
    )
    return json.loads(result["response"].read())


def _chat(body: dict) -> dict:
    message = body.get("message", "")
    if not message:
        return _response(400, {"error": "Request body must include a 'message' field."})
    conversation_id = body.get("conversation_id") or f"conv-{uuid.uuid4()}"
    payload = _invoke({"message": message, "conversation_id": conversation_id}, conversation_id)
    return _response(200, payload)


def _graph() -> dict:
    """The whole knowledge graph, read from the runtime that holds it in memory.

    Cannot be served from the bucket: the vault is markdown, and the parser
    lives in the runtime.
    """
    return _response(200, _invoke({"action": "graph"}, f"graph-{uuid.uuid4()}"))


def _manifest() -> dict:
    try:
        obj = _s3.get_object(Bucket=DATA_BUCKET, Key=MANIFEST_KEY)
    except ClientError as err:
        # No manifest yet: the corpus has never been indexed.
        if err.response["Error"]["Code"] in {"NoSuchKey", "404", "NotFound"}:
            return {}
        raise
    try:
        return json.loads(obj["Body"].read())
    except ValueError:
        return {}


def _list_cvs() -> dict:
    """Same shape as the runtime's CVLibrary, read straight from the bucket."""
    manifest = _manifest()
    people = {filename: person for person, filename in manifest.get("sources", {}).items()}
    cvs = []
    for page in _s3.get_paginator("list_objects_v2").paginate(Bucket=DATA_BUCKET, Prefix=CV_PREFIX):
        for obj in page.get("Contents", []):
            filename = obj["Key"][len(CV_PREFIX) :]
            if not filename or filename.endswith("/"):
                continue
            cvs.append(
                {
                    "filename": filename,
                    "size_bytes": obj["Size"],
                    "uploaded_at": obj["LastModified"].isoformat(timespec="seconds"),
                    "person": people.get(filename),
                }
            )
    cvs.sort(key=lambda cv: cv["filename"].lower())
    return _response(200, {"cvs": cvs, "indexed_at": manifest.get("stamp")})


def _schedule_reindex(context) -> None:
    """Drive the rebuild from a second, asynchronous invocation of this function
    so the browser is not left holding the request."""
    _lambda.invoke(
        FunctionName=context.invoked_function_arn,
        InvocationType="Event",
        Payload=json.dumps({"task": REINDEX_TASK}).encode(),
    )


def _cv_write(payload: dict, context, error_status: int = 400) -> dict:
    """Store or remove a CV on the runtime, then kick off the rebuild."""
    result = _invoke(payload, f"cvs-{uuid.uuid4()}")
    if "error" in result:
        return _response(error_status, {"error": result["error"]})
    _schedule_reindex(context)
    return _response(202, result)


def _upload_cv(body: dict, context) -> dict:
    filename = (body.get("filename") or "").strip()
    content_base64 = body.get("content_base64") or ""
    if not filename or not content_base64:
        return _response(
            400, {"error": "Request body must include 'filename' and 'content_base64'."}
        )
    if not filename.lower().endswith(SUPPORTED_SUFFIXES):
        return _response(
            400,
            {"error": f"Unsupported CV format — upload one of: {', '.join(SUPPORTED_SUFFIXES)}."},
        )
    try:
        size = len(base64.b64decode(content_base64, validate=True))
    except (ValueError, binascii.Error):
        return _response(400, {"error": "content_base64 is not valid base64."})
    if size > MAX_CV_BYTES:
        return _response(
            413, {"error": f"CVs must be smaller than {MAX_CV_BYTES // (1024 * 1024)} MB."}
        )
    return _cv_write(
        {"action": "add_cv", "filename": filename, "content_base64": content_base64}, context
    )


def _list_conversations() -> dict:
    items: list[dict] = []
    scan_kwargs = {
        "ProjectionExpression": "conversation_id, #t, updated_at",
        "ExpressionAttributeNames": {"#t": "title"},
    }
    while True:
        page = _table.scan(**scan_kwargs)
        items.extend(page.get("Items", []))
        last_key = page.get("LastEvaluatedKey")
        if not last_key:
            break
        scan_kwargs["ExclusiveStartKey"] = last_key
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return _response(
        200,
        [
            {
                "conversation_id": item["conversation_id"],
                "title": item.get("title", "Untitled"),
                "updated_at": item.get("updated_at", ""),
            }
            for item in items
        ],
    )


def _get_conversation(conversation_id: str) -> dict:
    item = _table.get_item(Key={"conversation_id": conversation_id}).get("Item")
    if item is None:
        return _response(404, {"detail": "Unknown conversation_id"})
    return _response(
        200,
        {
            "conversation_id": item["conversation_id"],
            "title": item.get("title", "Untitled"),
            "turns": item.get("turns", []),
        },
    )


def _delete_conversation(conversation_id: str) -> dict:
    _table.delete_item(Key={"conversation_id": conversation_id})
    return _response(200, {"deleted": conversation_id})


def _authenticate(event: dict) -> dict | None:
    """Return an error response when the request has no valid access token.

    Validated by calling Cognito's GetUser with the token — no JWT library, and
    so no bundling step for this asset directory.
    """
    if not USER_POOL_ID:
        return None
    header = (event.get("headers") or {}).get("authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return _response(401, {"error": "Missing or malformed Authorization header."})
    try:
        _cognito.get_user(AccessToken=token.strip())
    except ClientError as err:
        if err.response["Error"]["Code"] in {
            "NotAuthorizedException",
            "UserNotFoundException",
            "InvalidParameterException",
        }:
            return _response(401, {"error": "Invalid or expired session. Please sign in again."})
        raise
    return None


def handler(event: dict, context) -> dict:
    # Asynchronous self-invocation from _schedule_reindex, not an HTTP request.
    if event.get("task") == REINDEX_TASK:
        return _invoke({"action": REINDEX_TASK}, f"reindex-{uuid.uuid4()}")

    method = event["requestContext"]["http"]["method"]
    path = event["rawPath"]

    # Preflights carry no Authorization header, so they are answered by the
    # Function URL's CORS config before reaching any route.
    if method != "OPTIONS" and path != "/health":
        denied = _authenticate(event)
        if denied is not None:
            return denied

    body = {}
    if event.get("body"):
        raw = event["body"]
        if event.get("isBase64Encoded"):
            raw = base64.b64decode(raw)
        body = json.loads(raw)

    if method == "POST" and path == "/chat":
        return _chat(body)
    if method == "GET" and path == "/conversations":
        return _list_conversations()
    if method == "GET" and path == "/graph":
        return _graph()
    if method == "GET" and path == "/cvs":
        return _list_cvs()
    if method == "POST" and path == "/cvs":
        return _upload_cv(body, context)
    if method == "DELETE" and path.startswith("/cvs/"):
        filename = urllib.parse.unquote(path.split("/", 2)[2])
        return _cv_write({"action": "delete_cv", "filename": filename}, context, error_status=404)
    if path.startswith("/conversations/"):
        conversation_id = urllib.parse.unquote(path.split("/", 2)[2])
        if method == "GET":
            return _get_conversation(conversation_id)
        if method == "DELETE":
            return _delete_conversation(conversation_id)

    return _response(404, {"error": f"No route for {method} {path}"})
