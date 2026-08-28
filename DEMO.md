# TalentGraph — Demo Script

A 10–12 minute walkthrough for the viva, plus the questions you are most likely to
be asked and how to answer them.

## Before you start

- [ ] `make outputs` → copy the **SiteUrl**, open it in a browser tab and **send one
      question** to warm the runtime (the first request pays container cold start
      plus the vault download; you do not want that happening live).
- [ ] Second tab: the [Obsidian](https://obsidian.md) vault open on the graph view
      (open `vault/` as a vault, then ⌘G / the graph icon).
- [ ] Third tab: AWS console → CloudFormation → `TalentGraphStack` → Resources.
- [ ] Terminal in the repo root, with `data/cv_sources/alice_perera.txt` ready to show.
- [ ] Optional safety net: `make serve` + `make frontend-dev` running locally, so a
      network failure does not end the demo.

---

## 1 · The problem (1 min)

Open `data/cv_sources/alice_perera.txt` in the terminal or editor.

> "This is what capability data looks like in a real organisation: unstructured
> prose, every CV formatted differently. Notice this one says *Amazon Web
> Services* and *Natural Language Processing* — another says *AWS* and *NLP*.
> Answering 'who knows both Python and AWS' means a human opening every file.
> There is no structure and no relationships between documents."

## 2 · From CV to knowledge graph (2 min)

Show the pipeline in one command (already cached, so it is fast):

```bash
make ingest
```

> "Four stages. An LLM extracts entities under a Pydantic schema — so the output
> is a validated contract, not prose I have to parse. Each item carries a verbatim
> quote from the CV as evidence. Then normalisation collapses surface forms:
> a deterministic alias table first, then one LLM pass for the long tail. Then
> the writer emits Markdown notes where relationships are `[[Wikilinks]]`."

Open the generated note:

```bash
cat "vault/People/Alice Perera.md"
```

> "Frontmatter gives the node its type. Each section heading is a relation type —
> `## Skills` means HAS_SKILL, `## Projects` means WORKED_ON. The graph is not
> hidden in a database; it is human-readable Markdown in version control."

**Switch to Obsidian → graph view.**

> "And because it is an Obsidian vault, the knowledge graph is literally visible.
> These clusters are people; these hubs are shared skills and projects. This is
> the same structure my agents traverse — I can click any node and read the
> evidence behind it."

## 3 · Conversational querying (3 min)

**Switch to the deployed site.** Run these in order, in one conversation:

| # | Ask | Point to make |
| --- | --- | --- |
| 1 | *Who has both Python and AWS?* | Multi-constraint retrieval — expand the **Evidence** panel |
| 2 | *Which of them has AI experience?* | **Follow-up context** — "them" resolves from history |
| 3 | *How is Alice connected to NLP?* | **Graph path** evidence, not just a lookup |

On query 1, expand the evidence panel:

> "Every answer carries the graph relationships that produced it. Nothing here is
> the model's memory — it is traversal output. If the graph cannot support an
> answer, the system says so rather than speculating."

On query 2:

> "I never repeated the names. The orchestrator rewrote 'which of them' into a
> self-contained question using conversation history, which is persisted in
> DynamoDB keyed by conversation id."

## 4 · Reasoning, not just retrieval (2 min)

| # | Ask | Point to make |
| --- | --- | --- |
| 4 | *Build a three-person team for a project needing Python, AWS and React.* | Team composition + coverage + gaps |
| 5 | *Why would you select Alice over David for an AI project?* | Explainability with evidence |

> "Team composition is a greedy set-cover over the capability graph — it picks the
> person who adds the most *uncovered* capability, then reports what the team
> still lacks. That gap list is computed from the graph, not guessed."

On query 5:

> "This is the explainability requirement. Alice has ML and NLP skills plus an AI
> project; David has only 'basic machine learning' and no AI project. The system
> shows both sides of that comparison with the evidence, so a human makes the
> actual decision. It is advisory — it never accepts or rejects anyone, and it
> never ranks on protected attributes."

## 5 · The graph is live (1 min)

Open the **CV library** in the app. Upload a CV, or delete one.

> "The corpus is not static. Adding a CV runs the extraction pipeline and rebuilds
> the graph around it; deleting one reindexes without it. The knowledge graph is a
> living artefact, not a build-time asset."

## 6 · Cloud architecture (2 min)

**Switch to CloudFormation → `TalentGraphStack` → Resources.**

> "One CDK stack, everything reproducible — no console clicking. `cdk deploy`
> creates all of it and `cdk destroy` removes all of it."

Walk the request path:

> "The browser hits CloudFront. `/` serves the React SPA from S3. `/chat` routes to
> a Lambda proxy, which exists for a specific reason: invoking AgentCore requires
> SigV4-signed requests, and a browser cannot sign those. The proxy signs the call
> server-side. Because CloudFront fronts both, the SPA makes same-origin requests —
> no CORS, no hardcoded endpoint.
>
> The agent itself runs on Bedrock AgentCore Runtime as an arm64 container. At cold
> start it pulls the vault from S3 and holds the parsed graph in memory. The OpenAI
> key comes from SSM Parameter Store as a SecureString — it is never in the image,
> the template, or the repo."

Show `infrastructure/stacks/talentgraph_stack.py` briefly if asked.

## 7 · Evaluation and cost (1 min)

```bash
make eval
```

(Or show a pre-generated `EVALUATION.md` — do not run this live unless you have
time to spare.)

> "Fifteen benchmark questions with expected answers from a ground-truth file,
> scoring intent classification accuracy, retrieval precision and recall,
> groundedness and latency."

> "On cost: nothing is always-on. AgentCore bills per invocation, Lambda and
> DynamoDB are free at this volume, S3 and CloudFront are cents. Each question is
> about two `gpt-5-mini` calls — one to classify, one to synthesise. I deliberately
> avoided OpenSearch, RDS, ECS and a graph database, because at this corpus size
> they add cost and operational surface without improving answers."

---

## Anticipated questions

**Why Obsidian / Markdown instead of a graph database like Neo4j?**
The vault gives me a human-readable, version-controlled, visually inspectable
knowledge representation with zero infrastructure. For a corpus this size,
in-memory traversal with NetworkX is instant. Neo4j earns its place when the graph
outgrows memory or needs concurrent writes and Cypher — neither is true here, and
I can point at exactly what would change my mind.

**Why not RAG with a vector database?**
Because these are structural questions, not semantic-similarity questions. "Who has
both Python and AWS" is a set intersection over typed edges — exactly correct,
where embedding similarity is only approximately correct. The graph also produces
the *path* between two entities, which is what makes an answer explainable. Vector
search would help with fuzzy prose matching over a much larger corpus.

**Why LangGraph rather than a single prompt?**
Different question types need genuinely different retrieval. A team-composition
question runs set-cover over capabilities; a relationship question runs
path-finding. LangGraph gives me explicit intent classification, conditional
routing to specialist agents, and typed shared state for follow-ups — with each
step inspectable when something goes wrong.

**How do you stop it hallucinating?**
Three layers. Retrieval is deterministic graph traversal, so the facts come from
the vault, not the model. The synthesis prompt is constrained to supplied evidence
and instructed to say when the graph cannot answer. And every answer ships with the
relationships behind it, so a wrong claim is visible rather than plausible. The
`refusal-unknown` eval case checks exactly this.

**Why AgentCore instead of Lambda or ECS?**
It is a managed runtime purpose-built for agentic workloads — session isolation,
long-running invocations beyond typical API limits, and no cluster to operate. ECS
would mean managing a service for something that is idle most of the time; plain
Lambda is awkward for long agent turns.

**What are the limitations?**
Three honest ones. The `/chat` endpoint is unauthenticated — fine for fictional
data, but production needs Cognito or JWT inbound auth on AgentCore. The graph is
cached per container, so a re-index is picked up at the next cold start rather than
instantly. And extraction quality bounds everything downstream: a CV the model
misreads becomes a wrong edge, which is why every extracted item carries its source
quote for auditing.

**How would you scale this to 10,000 CVs?**
The in-memory graph stops being appropriate — I would move to a real graph store
and add vector search for fuzzy matching, keeping the Markdown vault as the
human-readable projection. Ingestion would become an async, parallel job. The agent
layer would not change, which is the point of keeping retrieval behind a clean
interface.

---

## If something breaks

| Symptom | Do this |
| --- | --- |
| Site times out on first message | Retry — it was a cold start; CloudFront caps origin responses at 60 s |
| Deployed site is down | Switch to the local tabs (`make serve` + `make frontend-dev`) and carry on |
| Answer looks wrong live | Open the evidence panel and reason about it out loud — showing you can audit the system is worth more than a perfect answer |
| Obsidian is not installed | Show a raw note in the editor and `vault/`'s directory structure instead |
