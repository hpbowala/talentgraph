import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../types";
import { trackSpotlight } from "../spotlight";

export function MessageView({ message }: { message: Message }) {
  if (message.role === "user") {
    return <div className="message user">{message.content}</div>;
  }
  if (message.role === "error") {
    return <div className="message error">{message.content}</div>;
  }
  return (
    <div className="message assistant spot" onMouseMove={trackSpotlight}>
      {message.intent && <span className="intent-chip">{message.intent}</span>}
      <div className="answer">
        <ReactMarkdown remarkPlugins={[remarkGfm]}>{message.content}</ReactMarkdown>
      </div>
      {message.evidence && message.evidence.length > 0 && (
        <details className="evidence">
          <summary>
            <span className="caret">▶</span>
            Evidence · {message.evidence.length} relation
            {message.evidence.length === 1 ? "" : "s"}
          </summary>
          <div className="evidence-list">
            {message.evidence.map((ref, i) => (
              <div className="evidence-line" key={i}>
                <span className="marker">·</span>
                <span>
                  {ref.detail}
                  {ref.source && <span className="source"> — {ref.source}</span>}
                </span>
              </div>
            ))}
          </div>
        </details>
      )}
    </div>
  );
}
