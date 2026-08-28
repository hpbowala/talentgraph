"""Terminal chat loop for development and demos.

Run from backend/: uv run talentgraph-chat
"""

import uuid

from app.service import handle_chat


def main() -> None:
    conversation_id = f"cli-{uuid.uuid4().hex[:8]}"
    print(f"TalentGraph chat (conversation {conversation_id}). Ctrl-D or 'exit' to quit.")
    while True:
        try:
            message = input("\nyou> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not message or message.lower() in {"exit", "quit"}:
            break
        response = handle_chat(message, conversation_id)
        print(f"\n[{response.intent}]")
        print(response.answer)
        if response.evidence:
            print("\nevidence:")
            for ref in response.evidence[:12]:
                print(f"  - {ref.detail}")


if __name__ == "__main__":
    main()
