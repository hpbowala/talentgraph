import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import type { Message } from "../types";
import { trackSpotlight } from "../spotlight";
import { parseEvidence } from "../evidence";

interface Props {
  message: Message;
  /** Opens the graph explorer on a note named in the evidence. */
  onShowInGraph?: (entity: string) => void;
}

export function MessageView({ message, onShowInGraph }: Props) {
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
                  {parseEvidence(ref.detail).map((segment, j) =>
                    segment.entity && onShowInGraph ? (
                      <button
                        key={j}
                        className="evidence-entity"
                        title={`Show ${segment.text} in the graph`}
                        onClick={() => onShowInGraph(segment.text)}
                      >
                        {segment.text}
                      </button>
                    ) : (
                      <span key={j}>{segment.text}</span>
                    ),
                  )}
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
