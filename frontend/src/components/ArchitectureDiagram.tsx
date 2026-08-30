import type { ReactNode } from "react";

/* The three figures on the architecture page, hand-drawn as inline SVG so they
   inherit the app's theme tokens (see the `.arch` block in index.css) and so the
   deployment figure can highlight one hop at a time.

   Coordinates are laid out on a grid: the request path runs left to right at
   y=194, the data tier sits in a band at y=444, and every connector is
   orthogonal. Keep it planar — the routes were chosen so no two lines cross. */

interface Hop {
  n: number;
  shape: ReactNode;
  badge: [number, number];
}

/** The numbered request path of Figure 1, in the order a question travels it.
 *  Kept in step with HOPS in Architecture.tsx — same numbers, same meaning. */
const HOPS: Hop[] = [
  { n: 1, shape: <polyline points="110,152 110,56 412,56" />, badge: [110, 112] },
  { n: 2, shape: <line x1={200} y1={194} x2={262} y2={194} />, badge: [231, 176] },
  { n: 3, shape: <line x1={374} y1={248} x2={374} y2={310} />, badge: [374, 276] },
  { n: 4, shape: <line x1={480} y1={194} x2={562} y2={194} />, badge: [521, 176] },
  { n: 5, shape: <polyline points="628,140 628,112 546,112 546,88" />, badge: [628, 126] },
  { n: 6, shape: <line x1={776} y1={194} x2={858} y2={194} />, badge: [817, 176] },
  { n: 7, shape: <polyline points="1145,262 1145,568 482,568 482,528" />, badge: [1145, 300] },
];

/** Which arrow labels belong to which hop, so they dim with their arrow. */
const HOP_LABELS: Record<number, ReactNode> = {
  1: (
    <>
      <text x={302} y={34} textAnchor="middle">
        sign in (SRP)
      </text>
      <text x={302} y={47} textAnchor="middle">
        access token
      </text>
    </>
  ),
  2: (
    <text x={231} y={212} textAnchor="middle">
      HTTPS
    </text>
  ),
  3: (
    <>
      <text x={390} y={272}>
        static SPA
      </text>
      <text x={390} y={286}>
        403 → /index.html
      </text>
    </>
  ),
  4: (
    <text x={521} y={212} textAnchor="middle">
      API routes
    </text>
  ),
  5: (
    <text x={587} y={103} textAnchor="middle">
      GetUser
    </text>
  ),
  6: (
    <>
      <text x={817} y={212} textAnchor="middle">
        SigV4
      </text>
      <text x={817} y={226} textAnchor="middle">
        invoke
      </text>
    </>
  ),
  7: (
    <text x={813} y={558} textAnchor="middle">
      writes each chat turn
    </text>
  ),
};

interface DeploymentProps {
  /** Hop to spotlight, or null for the whole diagram at equal weight. */
  hop: number | null;
  onHop: (n: number | null) => void;
}

export function DeploymentDiagram({ hop, onHop }: DeploymentProps) {
  return (
    <svg
      className={hop === null ? "arch-svg" : "arch-svg spotlit"}
      viewBox="0 0 1380 620"
      role="img"
      aria-label="TalentGraph on AWS. A browser signs in to an Amazon Cognito user pool and calls one CloudFront distribution, which serves the React app from an S3 site bucket and routes the API paths to an AWS Lambda function URL. The Lambda validates the token with Cognito, reads DynamoDB and the S3 data bucket directly, and makes SigV4-signed InvokeAgentRuntime calls to an Amazon Bedrock AgentCore Runtime. The runtime reads the vault from S3 and the OpenAI key from Parameter Store, writes each chat turn to DynamoDB, and calls OpenAI outside the AWS account boundary."
    >
      <defs>
        <marker
          id="arch-tip-flow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-flow)" />
        </marker>
        <marker
          id="arch-tip-data"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6.5"
          markerHeight="6.5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-data)" />
        </marker>
        <marker
          id="arch-tip-async"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-async)" />
        </marker>
        <marker
          id="arch-tip-ext"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-ext)" />
        </marker>
      </defs>

      <g fontFamily="var(--font-mono)">
        {/* account boundary */}
        <rect
          x={232}
          y={6}
          width={968}
          height={596}
          rx={16}
          fill="none"
          stroke="var(--arch-data)"
          strokeWidth={1.5}
          strokeDasharray="7 6"
          opacity="0.45"
        />
        <text x={1184} y={28} textAnchor="end" fontSize={11} fill="var(--arch-sub)" letterSpacing="1.4">
          AWS ACCOUNT · us-east-1
        </text>

        {/* ---- nodes ---- */}
        <g className="arch-node">
          <rect x={20} y={152} width={180} height={84} rx={10} />
          <text className="arch-eyebrow" x={38} y={176}>
            CLIENT
          </text>
          <text className="arch-title" x={38} y={198}>
            Browser
          </text>
          <text className="arch-sub" x={38} y={218}>
            React 19 SPA · Vite
          </text>
        </g>

        <g className="arch-node">
          <rect x={420} y={26} width={240} height={60} rx={10} />
          <text className="arch-eyebrow" x={438} y={46}>
            AUTH
          </text>
          <text className="arch-title" x={438} y={66}>
            Amazon Cognito
          </text>
          <text className="arch-sub" x={438} y={80}>
            user pool · sign-up disabled
          </text>
        </g>

        <g className="arch-node">
          <rect x={268} y={140} width={212} height={108} rx={10} />
          <text className="arch-eyebrow" x={286} y={162}>
            EDGE
          </text>
          <text className="arch-title" x={286} y={184}>
            Amazon CloudFront
          </text>
          <text className="arch-sub" x={286} y={205}>
            / → S3 site bucket
          </text>
          <text className="arch-sub" x={286} y={220}>
            /chat /conversations*
          </text>
          <text className="arch-sub" x={286} y={235}>
            /cvs* /graph → Lambda
          </text>
        </g>

        <g className="arch-node">
          <rect x={568} y={140} width={208} height={108} rx={10} />
          <text className="arch-eyebrow" x={586} y={162}>
            API
          </text>
          <text className="arch-title" x={586} y={184}>
            AWS Lambda
          </text>
          <text className="arch-sub" x={586} y={205}>
            Function URL · py3.13
          </text>
          <text className="arch-sub" x={586} y={220}>
            validates every token
          </text>
          <text className="arch-sub" x={586} y={235}>
            signs SigV4 requests
          </text>
        </g>

        <g className="arch-node lit">
          <rect x={864} y={126} width={296} height={136} rx={10} />
          <text className="arch-eyebrow on" x={882} y={148}>
            COMPUTE
          </text>
          <text className="arch-title" x={882} y={170}>
            Amazon Bedrock
          </text>
          <text className="arch-title" x={882} y={188}>
            AgentCore Runtime
          </text>
          <text className="arch-sub" x={882} y={211}>
            arm64 container · image in ECR
          </text>
          <text className="arch-sub" x={882} y={228}>
            LangGraph orchestrator + agents
          </text>
          <text className="arch-sub" x={882} y={245}>
            logs + traces → CloudWatch, X-Ray
          </text>
        </g>

        {/* external — outside the account boundary */}
        <rect
          x={1218}
          y={166}
          width={142}
          height={56}
          rx={10}
          fill="none"
          stroke="var(--arch-ext)"
          strokeDasharray="5 4"
        />
        <text x={1234} y={188} fontSize={14} fontFamily="var(--font-sans)" fontWeight={600} fill="var(--arch-ext)">
          OpenAI
        </text>
        <text className="arch-sub" x={1234} y={205}>
          gpt-5-mini
        </text>

        <g className="arch-node">
          <rect x={268} y={316} width={212} height={76} rx={10} />
          <text className="arch-eyebrow" x={286} y={338}>
            STATIC HOSTING
          </text>
          <text className="arch-title" x={286} y={360}>
            Amazon S3
          </text>
          <text className="arch-sub" x={286} y={379}>
            site bucket · OAC only
          </text>
        </g>

        <g className="arch-node">
          <rect x={420} y={444} width={210} height={80} rx={10} />
          <text className="arch-eyebrow" x={438} y={466}>
            STATE
          </text>
          <text className="arch-title" x={438} y={488}>
            Amazon DynamoDB
          </text>
          <text className="arch-sub" x={438} y={507}>
            conversations · on-demand
          </text>
        </g>

        <g className="arch-node">
          <rect x={676} y={444} width={224} height={80} rx={10} />
          <text className="arch-eyebrow" x={694} y={466}>
            SOURCE OF TRUTH
          </text>
          <text className="arch-title" x={694} y={488}>
            Amazon S3
          </text>
          <text className="arch-sub" x={694} y={507}>
            cvs/ · vault/ · profiles/
          </text>
        </g>

        <g className="arch-node">
          <rect x={940} y={444} width={190} height={80} rx={10} />
          <text className="arch-eyebrow" x={958} y={466}>
            AWS SSM
          </text>
          <text className="arch-title" x={958} y={488}>
            Parameter Store
          </text>
          <text className="arch-sub" x={958} y={507}>
            OpenAI key · SecureString
          </text>
        </g>

        {/* ---- data plane ---- */}
        <g
          className="arch-data-lines"
          stroke="var(--arch-data)"
          strokeWidth={1.6}
          fill="none"
          markerEnd="url(#arch-tip-data)"
        >
          <polyline points="610,248 610,410 525,410 525,440" />
          <polyline points="730,248 730,410 800,410 800,440" />
          <polyline points="890,262 890,428 858,428 858,440" />
          <line x1={1035} y1={262} x2={1035} y2={440} />
        </g>
        <g className="arch-data-lines" fontSize={11} fill="var(--arch-sub)">
          <text x={568} y={398} textAnchor="middle">
            conversations
          </text>
          <text x={806} y={400}>
            cvs/ listing
          </text>
          <text x={902} y={330}>
            reads vault/
          </text>
          <text x={902} y={344}>
            writes cvs/ vault/
          </text>
          <text x={1047} y={330}>
            OpenAI key
          </text>
          <text x={1047} y={344}>
            at cold start
          </text>
        </g>

        {/* ---- external + asynchronous ---- */}
        <g className="arch-aux">
        <line
          x1={1160}
          y1={194}
          x2={1212}
          y2={194}
          stroke="var(--arch-ext)"
          strokeWidth={2}
          markerEnd="url(#arch-tip-ext)"
        />
        <text x={1186} y={212} textAnchor="middle" fontSize={11} fill="var(--arch-ext)">
          HTTPS
        </text>

        <polyline
          points="776,166 812,166 812,108 690,108 690,140"
          fill="none"
          stroke="var(--arch-async)"
          strokeWidth={2}
          strokeDasharray="6 5"
          markerEnd="url(#arch-tip-async)"
        />
        <text x={751} y={99} textAnchor="middle" fontSize={11} fill="var(--arch-async)">
          async reindex
        </text>
        </g>

        {/* ---- request path ---- */}
        <g stroke="var(--arch-flow)" strokeWidth={2} fill="none" markerEnd="url(#arch-tip-flow)">
          {HOPS.map((h) => (
            <g key={h.n} className={hop === h.n ? "arch-hop on" : "arch-hop"}>
              {h.shape}
            </g>
          ))}
        </g>
        <g fontSize={11} fill="var(--arch-flow)">
          {HOPS.map((h) => (
            <g key={h.n} className={hop === h.n ? "arch-hop on" : "arch-hop"}>
              {HOP_LABELS[h.n]}
            </g>
          ))}
        </g>

        {/* badges last, so a connector never draws over its own number */}
        <g aria-hidden="true">
          {HOPS.map((h) => (
            <g
              key={h.n}
              className={hop === h.n ? "arch-badge on" : "arch-badge"}
              onMouseEnter={() => onHop(h.n)}
              onMouseLeave={() => onHop(null)}
            >
              <circle cx={h.badge[0]} cy={h.badge[1]} r={11} />
              <text x={h.badge[0]} y={h.badge[1] + 4} textAnchor="middle" fontSize={11.5}>
                {h.n}
              </text>
            </g>
          ))}
        </g>
      </g>
    </svg>
  );
}

export function RuntimeDiagram() {
  return (
    <svg
      className="arch-svg"
      viewBox="0 0 1180 360"
      role="img"
      aria-label="Inside the AgentCore runtime: a question enters a LangGraph orchestrator that classifies intent with one LLM call, routes to a People, Skill and graph, Team or General node, each of which queries an in-memory NetworkX graph retriever, and returns evidence to a grounded synthesis step that writes the answer with one more LLM call."
    >
      <defs>
        <marker
          id="arch-rt-flow"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-flow)" />
        </marker>
        <marker
          id="arch-rt-data"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="6.5"
          markerHeight="6.5"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-data)" />
        </marker>
      </defs>

      <g fontFamily="var(--font-mono)">
        <g className="arch-node">
          <rect x={14} y={146} width={132} height={56} rx={28} />
          <text className="arch-title" x={80} y={171} textAnchor="middle" fontSize={13}>
            Question
          </text>
          <text className="arch-sub" x={80} y={188} textAnchor="middle" fontSize={10.5}>
            + history
          </text>
        </g>

        <g className="arch-node lit">
          <rect x={200} y={124} width={190} height={100} rx={10} />
          <text className="arch-title" x={216} y={150} fontSize={14}>
            Orchestrator
          </text>
          <text className="arch-sub" x={216} y={171}>
            classify intent (LLM)
          </text>
          <text className="arch-sub" x={216} y={187}>
            resolve follow-ups
          </text>
          <text className="arch-sub" x={216} y={203}>
            route + synthesise
          </text>
        </g>

        <g className="arch-node">
          <rect x={450} y={39} width={190} height={54} rx={10} />
          <text className="arch-title" x={466} y={62} fontSize={13}>
            People agent
          </text>
          <text className="arch-sub" x={466} y={80} fontSize={10.5}>
            lookup · capability match
          </text>
        </g>
        <g className="arch-node">
          <rect x={450} y={111} width={190} height={54} rx={10} />
          <text className="arch-title" x={466} y={134} fontSize={13}>
            Skill / graph agent
          </text>
          <text className="arch-sub" x={466} y={152} fontSize={10.5}>
            relationships · paths
          </text>
        </g>
        <g className="arch-node">
          <rect x={450} y={183} width={190} height={54} rx={10} />
          <text className="arch-title" x={466} y={206} fontSize={13}>
            Team agent
          </text>
          <text className="arch-sub" x={466} y={224} fontSize={10.5}>
            ranking · gaps
          </text>
        </g>
        <g className="arch-node">
          <rect x={450} y={255} width={190} height={54} rx={10} />
          <text className="arch-title" x={466} y={278} fontSize={13}>
            General
          </text>
          <text className="arch-sub" x={466} y={296} fontSize={10.5}>
            fallback · out of scope
          </text>
        </g>

        <g className="arch-node">
          <rect x={700} y={124} width={190} height={100} rx={10} />
          <text className="arch-title" x={716} y={150} fontSize={14}>
            Graph retriever
          </text>
          <text className="arch-sub" x={716} y={171}>
            NetworkX MultiDiGraph
          </text>
          <text className="arch-sub" x={716} y={187}>
            parsed from vault/
          </text>
          <text className="arch-sub" x={716} y={203}>
            held in memory
          </text>
        </g>

        <g className="arch-node lit">
          <rect x={950} y={124} width={190} height={100} rx={10} />
          <text className="arch-title" x={966} y={150} fontSize={14}>
            Synthesis
          </text>
          <text className="arch-sub" x={966} y={171}>
            LLM constrained to
          </text>
          <text className="arch-sub" x={966} y={187}>
            retrieved evidence
          </text>
          <text className="arch-sub" x={966} y={203}>
            refuses when unsupported
          </text>
        </g>

        <g stroke="var(--arch-flow)" strokeWidth={2} fill="none" markerEnd="url(#arch-rt-flow)">
          <line x1={146} y1={174} x2={194} y2={174} />
          <path d="M390 174 C 418 174, 420 66, 444 66" />
          <path d="M390 174 C 418 174, 420 138, 444 138" />
          <path d="M390 174 C 418 174, 420 210, 444 210" />
          <path d="M390 174 C 418 174, 420 282, 444 282" />
          <line x1={890} y1={174} x2={944} y2={174} />
          <line x1={1140} y1={174} x2={1176} y2={174} />
        </g>
        <g stroke="var(--arch-data)" strokeWidth={1.6} fill="none" markerEnd="url(#arch-rt-data)">
          <path d="M640 66 C 668 66, 670 148, 694 148" />
          <path d="M640 138 C 668 138, 670 164, 694 164" />
          <path d="M640 210 C 668 210, 670 186, 694 186" />
          <path d="M640 282 C 668 282, 670 202, 694 202" />
        </g>

        <g fontSize={11}>
          <text x={410} y={140} textAnchor="middle" fill="var(--arch-flow)">
            route
          </text>
          <text x={917} y={166} textAnchor="middle" fill="var(--arch-flow)">
            evidence
          </text>
          <text x={295} y={243} textAnchor="middle" fontSize={10.5} fill="var(--arch-sub)">
            1 LLM call
          </text>
          <text x={1045} y={243} textAnchor="middle" fontSize={10.5} fill="var(--arch-sub)">
            1 LLM call
          </text>
          <text x={1176} y={196} textAnchor="end" fontSize={10.5} fill="var(--arch-sub)">
            answer
          </text>
        </g>
      </g>
    </svg>
  );
}

const WRITE_STEPS = [
  { x: 10, n: 1, title: "Upload", lines: ["POST /cvs", "pdf · txt · md, base64", "≤ 4 MB"] },
  { x: 255, n: 2, title: "202 Accepted", lines: ["Lambda → runtime", "action: add_cv", "browser is freed"] },
  { x: 500, n: 3, title: "Stored", lines: ["S3 data bucket", "cvs/<filename>", "graph not yet changed"] },
  { x: 745, n: 4, title: "Rebuild", lines: ["async self-invoke", "extract → normalise", "→ write vault/"] },
  { x: 970, n: 5, title: "Published", lines: ["vault/.index.json", "stamp moves", "SPA polls GET /cvs"] },
];

export function WritePathDiagram() {
  return (
    <svg
      className="arch-svg"
      viewBox="0 0 1180 158"
      role="img"
      aria-label="The CV write path in five steps: the browser posts a base64 CV, the Lambda stores it through the runtime and returns 202 Accepted, the runtime writes the file to the S3 data bucket, the Lambda invokes itself asynchronously to drive extraction and the vault rebuild, and the browser polls until the index stamp moves."
    >
      <defs>
        <marker
          id="arch-wp-async"
          viewBox="0 0 10 10"
          refX="9"
          refY="5"
          markerWidth="7"
          markerHeight="7"
          orient="auto-start-reverse"
        >
          <path d="M0 0 L10 5 L0 10 z" fill="var(--arch-async)" />
        </marker>
      </defs>

      <g fontFamily="var(--font-mono)" transform="translate(0,-26)">
        {WRITE_STEPS.map((s) => (
          <g key={s.n} className="arch-node">
            <rect x={s.x} y={46} width={200} height={112} rx={10} />
            <text className="arch-title" x={s.x + 46} y={75} fontSize={13}>
              {s.title}
            </text>
            {s.lines.map((line, i) => (
              <text className="arch-sub" key={line} x={s.x + 20} y={106 + i * 17}>
                {line}
              </text>
            ))}
          </g>
        ))}

        <g
          stroke="var(--arch-async)"
          strokeWidth={2}
          fill="none"
          strokeDasharray="6 5"
          markerEnd="url(#arch-wp-async)"
        >
          <line x1={210} y1={102} x2={249} y2={102} />
          <line x1={455} y1={102} x2={494} y2={102} />
          <line x1={700} y1={102} x2={739} y2={102} />
          <line x1={945} y1={102} x2={964} y2={102} />
        </g>

        <g className="arch-badge async" aria-hidden="true">
          {WRITE_STEPS.map((s) => (
            <g key={s.n}>
              <circle cx={s.x + 24} cy={70} r={11} />
              <text x={s.x + 24} y={74} textAnchor="middle" fontSize={11.5}>
                {s.n}
              </text>
            </g>
          ))}
        </g>
      </g>
    </svg>
  );
}
