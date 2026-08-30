"""Conversation persistence (chat history / threads).

Two backends, selected by CONVERSATION_STORE:
- "memory" (default): per-process dict, for local dev.
- "dynamodb": one item per conversation, table created on first use.
"""

import os

STORE_BACKEND = os.getenv("CONVERSATION_STORE", "memory")
TABLE_NAME = os.getenv("CONVERSATIONS_TABLE", "talentgraph-conversations")

_memory: dict[str, dict] = {}
_table = None


def _get_table():
    import boto3  # noqa: PLC0415 — only needed for the dynamodb backend
    from botocore.exceptions import ClientError  # noqa: PLC0415

    global _table
    if _table is None:
        dynamodb = boto3.resource("dynamodb")
        table = dynamodb.Table(TABLE_NAME)
        try:
            table.load()
        except ClientError as err:
            if err.response["Error"]["Code"] != "ResourceNotFoundException":
                raise
            table = dynamodb.create_table(
                TableName=TABLE_NAME,
                KeySchema=[{"AttributeName": "conversation_id", "KeyType": "HASH"}],
                AttributeDefinitions=[{"AttributeName": "conversation_id", "AttributeType": "S"}],
                BillingMode="PAY_PER_REQUEST",
            )
            table.wait_until_exists()
        _table = table
    return _table


def fetch(conversation_id: str) -> dict | None:
    """Return the full conversation item, or None if it does not exist."""
    if STORE_BACKEND == "memory":
        return _memory.get(conversation_id)
    response = _get_table().get_item(Key={"conversation_id": conversation_id})
    return response.get("Item")


def save(conversation: dict) -> None:
    if STORE_BACKEND == "memory":
        _memory[conversation["conversation_id"]] = conversation
        return
    _get_table().put_item(Item=conversation)


def list_summaries() -> list[dict]:
    """All conversations (id, title, updated_at), most recently updated first."""
    if STORE_BACKEND == "memory":
        items = [
            {
                "conversation_id": item["conversation_id"],
                "title": item.get("title", "Untitled"),
                "updated_at": item.get("updated_at", ""),
            }
            for item in _memory.values()
        ]
    else:
        table = _get_table()
        kwargs: dict = {
            "ProjectionExpression": "conversation_id, #t, #u",
            "ExpressionAttributeNames": {"#t": "title", "#u": "updated_at"},
        }
        items = []
        while True:
            response = table.scan(**kwargs)
            items.extend(response.get("Items", []))
            last_key = response.get("LastEvaluatedKey")
            if not last_key:
                break
            kwargs["ExclusiveStartKey"] = last_key
    items.sort(key=lambda item: item.get("updated_at", ""), reverse=True)
    return items


def delete(conversation_id: str) -> None:
    if STORE_BACKEND == "memory":
        _memory.pop(conversation_id, None)
        return
    _get_table().delete_item(Key={"conversation_id": conversation_id})
