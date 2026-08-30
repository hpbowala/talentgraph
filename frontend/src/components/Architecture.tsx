import { useState } from "react";
import { useNavigate } from "react-router-dom";
import { DeploymentDiagram, RuntimeDiagram, WritePathDiagram } from "./ArchitectureDiagram";
import { Brand } from "./Sidebar";
import { useSession } from "../session-context";

/* Public documentation route at /architecture. It describes the system rather
   than reading from it, so it needs no session and no API call — which is what
   lets a signed-out visitor follow "Explore the architecture" from the landing
   page. Every claim here is drawn from infrastructure/stacks/talentgraph_stack.py
   and infrastructure/proxy/handler.py; change those and change this. */

const FACTS = [
  ["Region", "us-east-1"],
  ["IaC", "AWS CDK (Python)"],
  ["Compute", "Bedrock AgentCore"],
  ["Image", "linux/arm64"],
  ["Always-on cost", "none"],
];

/** Numbered to match the badges in the deployment figure. */
const HOPS = [
  {
    n: 1,
    title: "Sign in",
    body: "The SPA runs the SRP exchange against the Cognito user pool, so the password is proven without being sent. The pool returns a one-hour access token. Sign-up is disabled — the operator account is created out of band.",
  },
  {
    n: 2,
    title: "Request",
    body: "Every call goes to the one CloudFront domain over HTTPS, carrying the access token as a bearer credential.",
  },
  {
    n: 3,
    title: "Static SPA",
    body: "The default behaviour serves the React build from a private S3 bucket through Origin Access Control. S3 answers 403 for an unknown key, and the distribution rewrites that to /index.html with a 200 — which is what makes a refresh on /app work.",
  },
  {
    n: 4,
    title: "API routes",
    body: "/chat, /conversations*, /cvs* and /graph are separate behaviours pointed at the Lambda Function URL, caching disabled. The chat screen lives at /app, not /chat, precisely because /chat is claimed by the API.",
  },
  {
    n: 5,
    title: "Token check",
    body: "The proxy calls Cognito GetUser with the caller's token — signature, expiry and revocation settled in one call, with no JWT library to bundle. No valid token, no answer: 401.",
  },
  {
    n: 6,
    title: "Invoke",
    body: "The proxy SigV4-signs InvokeAgentRuntime. AgentCore exposes a single route, so operations are multiplexed through an action field on the payload.",
  },
  {
    n: 7,
    title: "Persist",
    body: "The runtime answers from the in-memory graph and writes the turn — question, answer, intent and evidence — to DynamoDB. The proxy reads that same table directly, so browsing history costs no invocation.",
  },
];

const SERVICES = [
  {
    name: "Amazon CloudFront",
    kind: "Distribution",
    role: "The single public entry point. The default behaviour serves the SPA; four more route the API paths to the Lambda origin.",
    why: "One origin for site and API means the SPA makes same-origin calls — no CORS, no baked-in endpoint, TLS for free.",
  },
  {
    name: "Amazon S3",
    kind: "Site bucket",
    role: "Holds the built React bundle. Private, block-all-public-access, reachable only through CloudFront OAC.",
    why: "Static hosting with nothing to run. Rewritten by every deploy, so it holds nothing worth retaining.",
  },
  {
    name: "Amazon S3",
    kind: "Data bucket",
    role: "cvs/ the corpus, vault/ the generated knowledge graph, profiles/ the cached extractions.",
    why: "The vault is the product artefact — plain Markdown, diff-able, openable in Obsidian. S3 makes it readable by every runtime instance at once.",
  },
  {
    name: "Amazon Cognito",
    kind: "User pool + SPA client",
    role: "SRP sign-in from the browser; the access token gates every API route except /health.",
    why: "The site sits on a public URL, so possession of credentials — not knowledge of the URL — has to be what grants access.",
  },
  {
    name: "AWS Lambda",
    kind: "Function URL",
    role: "The browser-facing API: validates tokens, serves conversation CRUD and the CV listing, signs runtime invocations, and drives reindexing asynchronously.",
    why: "A browser cannot SigV4-sign a request. Since the proxy is the only route to the data, it is also the one place the auth gate has to go.",
  },
  {
    name: "Amazon Bedrock",
    kind: "AgentCore Runtime",
    role: "Runs the LangGraph application as an arm64 container serving /invocations and /ping.",
    why: "Purpose-built agent hosting: no cluster to size, no load balancer, scales to zero, billed per invocation.",
  },
  {
    name: "Amazon ECR",
    kind: "Private repository",
    role: "Stores the runtime image, built and pushed by CDK as a Docker image asset during deploy.",
    why: "The image carries no dataset, so it stays independent of the corpus it serves.",
  },
  {
    name: "Amazon DynamoDB",
    kind: "On-demand table",
    role: "Conversation history — turns, intents and evidence — keyed by conversation_id.",
    why: "Key-value access by conversation id is all the app needs, and on-demand billing costs effectively nothing at this volume.",
  },
  {
    name: "AWS Systems Manager",
    kind: "Parameter Store",
    role: "Holds the OpenAI API key as a SecureString, fetched by the runtime at start.",
    why: "The key never enters the CloudFormation template, the image, or the repository.",
  },
  {
    name: "Amazon CloudWatch",
    kind: "+ AWS X-Ray",
    role: "Runtime logs, metrics and traces; Lambda logs.",
    why: "The runtime is a black box otherwise — an ingestion run's progress is only visible in its logs.",
  },
  {
    name: "AWS IAM",
    kind: "Task-scoped roles",
    role: "A runtime role (S3, DynamoDB, SSM, ECR pull, logs) and a proxy role (invoke runtime, DynamoDB, S3 read, self-invoke).",
    why: "Each role carries only the actions its component performs, resource-scoped by ARN rather than wildcarded.",
  },
  {
    name: "AWS CloudFormation",
    kind: "via AWS CDK (Python)",
    role: "Defines every resource above, plus the image build and the SPA deployment, in one stack.",
    why: "Nothing is configured in the console. Resource names come from backend/.env, so backend and infrastructure agree by construction.",
  },
];

const OPERATIONS = [
  {
    title: "Cold start",
    body: "The runtime downloads the vault from S3 and parses it once, then holds the graph for the container's life. Warm questions touch no storage but DynamoDB.",
  },
  {
    title: "Cost",
    body: "Nothing is always-on. AgentCore bills per invocation, Lambda and DynamoDB are effectively free at this volume, and a question is roughly two model calls.",
  },
  {
    title: "Data retention",
    body: "The data bucket, conversations table and user pool are all RETAIN, so neither a teardown nor a replacement-forcing change can take the data or the accounts with it.",
  },
  {
    title: "Reproducibility",
    body: "One stack, one region, no console steps. A clean install deploys twice only because the SPA bundle needs the Cognito pool ids the first deploy creates.",
  },
];

export function Architecture() {
  const navigate = useNavigate();
  const { status } = useSession();
  const [pinned, setPinned] = useState<number | null>(null);
  const [hovered, setHovered] = useState<number | null>(null);
  // Hover previews a hop; a click keeps it lit, which is the only way to hold
  // one open on a touch screen.
  const hop = hovered ?? pinned;

  const signedIn = status === "in";
  const back = () => navigate(signedIn ? "/app" : "/");

  return (
    <div className="arch">
      <div className="ambient" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
      </div>

      <header className="landing-bar">
        <Brand />
        <button className="landing-cta ghost" onClick={back}>
          {signedIn ? "Back to the app" : "Back"}
        </button>
      </header>

      <main className="arch-main">
        <section className="arch-hero">
          <div className="arch-overline">Cloud deployment</div>
          <h2>How TalentGraph runs on AWS.</h2>
          <p className="arch-lede">
            One CDK stack, twelve AWS services, and nothing always-on. Every request the
            browser makes arrives through a single CloudFront domain; the agent runtime
            behind it has no public listener at all.
          </p>
          <ul className="arch-facts">
            {FACTS.map(([k, v]) => (
              <li key={k}>
                {k} <b>{v}</b>
              </li>
            ))}
          </ul>
        </section>

        <section className="arch-section">
          <h3>System architecture</h3>
          <p className="arch-note">
            Hover or tap a step below — or a number in the diagram — to trace it
            through the system.
          </p>

          <figure className="arch-figure">
            <ul className="arch-legend">
              <li>
                <i className="k-flow" /> request path
              </li>
              <li>
                <i className="k-data" /> data access
              </li>
              <li>
                <i className="k-async" /> asynchronous
              </li>
              <li>
                <i className="k-ext" /> external service
              </li>
              <li>
                <i className="k-bound" /> AWS account boundary
              </li>
            </ul>
            <div className="arch-canvas">
              <DeploymentDiagram hop={hop} onHop={setHovered} />
            </div>
          </figure>

          <ol className="arch-hops">
            {HOPS.map((h) => (
              <li key={h.n}>
                <button
                  className={hop === h.n ? "arch-hop-item on" : "arch-hop-item"}
                  aria-pressed={pinned === h.n}
                  onMouseEnter={() => setHovered(h.n)}
                  onMouseLeave={() => setHovered(null)}
                  onFocus={() => setHovered(h.n)}
                  onBlur={() => setHovered(null)}
                  onClick={() => setPinned(pinned === h.n ? null : h.n)}
                >
                  <span className="arch-hop-n">{h.n}</span>
                  <span>
                    <b>{h.title}</b>
                    {h.body}
                  </span>
                </button>
              </li>
            ))}
          </ol>
        </section>

        <section className="arch-section">
          <h3>Inside the runtime</h3>
          <p className="arch-note">
            The container is a LangGraph state graph. Retrieval is deterministic traversal
            over a NetworkX graph parsed from the Markdown vault — not vector search — so an
            answer can carry the exact relationships that justify it.
          </p>
          <figure className="arch-figure">
            <div className="arch-canvas">
              <RuntimeDiagram />
            </div>
            <figcaption>
              Two model calls per question: one to classify, one to synthesise. Everything
              between them is graph traversal, which is what makes <em>who has both Python and
              AWS?</em> a set intersection rather than a similarity score.
            </figcaption>
          </figure>
        </section>

        <section className="arch-section">
          <h3>Adding a CV</h3>
          <p className="arch-note">
            Storing a CV is quick; rebuilding the graph around it takes minutes — far longer
            than CloudFront's 60-second origin timeout. So the write returns immediately and
            the rebuild runs off-request.
          </p>
          <figure className="arch-figure">
            <div className="arch-canvas">
              <WritePathDiagram />
            </div>
            <figcaption>
              The proxy invokes itself asynchronously to drive the rebuild, so no browser
              request is left hanging. Every runtime instance compares the published stamp
              before answering — so the stamp, not the container, is what says which graph is
              current.
            </figcaption>
          </figure>
        </section>

        <section className="arch-section">
          <h3>The services, and what each is for</h3>
          <div className="arch-table-wrap">
            <table className="arch-table">
              <thead>
                <tr>
                  <th>Service</th>
                  <th>Role in TalentGraph</th>
                  <th>Why this one</th>
                </tr>
              </thead>
              <tbody>
                {SERVICES.map((s) => (
                  <tr key={`${s.name} ${s.kind}`}>
                    <td className="arch-svc">
                      {s.name}
                      <span>{s.kind}</span>
                    </td>
                    <td>{s.role}</td>
                    <td className="arch-why">{s.why}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>


        <section className="arch-section">
          <h3>Operational characteristics</h3>
          <div className="arch-ops">
            {OPERATIONS.map((o) => (
              <article key={o.title}>
                <h4>{o.title}</h4>
                <p>{o.body}</p>
              </article>
            ))}
          </div>
        </section>
      </main>

      <footer className="landing-foot">
        An advisory prototype built on fictional CVs. It makes no hiring decisions and ranks
        nobody on protected attributes.
      </footer>
    </div>
  );
}
