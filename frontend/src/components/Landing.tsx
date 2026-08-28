import { useNavigate } from "react-router-dom";
import { Brand } from "./Sidebar";
import { useSession } from "../session-context";
import { trackSpotlight } from "../spotlight";

const CAPABILITIES = [
  {
    title: "A graph, not a black box",
    body: "Every CV becomes Markdown notes linked by wikilinks. The knowledge graph is a real artefact you can open, read and diff — not a hidden index.",
  },
  {
    title: "Answers with evidence",
    body: "Each response carries the graph relationships that justify it, and says so plainly when the graph cannot support an answer.",
  },
  {
    title: "Specialist agents",
    body: "A LangGraph orchestrator classifies each question and routes it to people lookup, relationship search or team composition.",
  },
];

const SAMPLE_QUESTIONS = [
  "Who has both Python and AWS?",
  "How is Alice connected to NLP?",
  "Build a three-person team for Python, AWS and React",
];

/** Public front door at `/`. Entirely static apart from the call to action, so
 *  it renders for signed-out visitors without touching the API. */
export function Landing() {
  const navigate = useNavigate();
  const { required } = useSession();
  // With no user pool there is nothing to sign in to, so the button opens the
  // app directly rather than leading to a login form that cannot work.
  const ctaLabel = required ? "Sign in" : "Open the app";
  const onEnter = () => navigate(required ? "/login" : "/app");

  return (
    <div className="landing">
      <div className="ambient" aria-hidden="true">
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
        <div className="blob blob-d" />
      </div>

      <header className="landing-bar">
        <Brand />
        <button className="landing-cta ghost" onClick={onEnter}>
          {ctaLabel}
        </button>
      </header>

      <main className="landing-main">
        <section className="landing-hero">
          <div className="overline">Workforce Intelligence</div>
          <h2>Ask your organisation who can build what.</h2>
          <p className="landing-lede">
            TalentGraph turns unstructured employee CVs into a queryable knowledge graph of
            people, skills, projects and technologies — then answers questions about it in
            plain English.
          </p>
          <button className="landing-cta spot" onClick={onEnter} onMouseMove={trackSpotlight}>
            {ctaLabel}
          </button>
        </section>

        <section className="landing-grid">
          {CAPABILITIES.map((c) => (
            <article key={c.title} className="landing-card">
              <h3>{c.title}</h3>
              <p>{c.body}</p>
            </article>
          ))}
        </section>

        <section className="landing-questions">
          <div className="overline">Questions it answers</div>
          <ul>
            {SAMPLE_QUESTIONS.map((q) => (
              <li key={q}>{q}</li>
            ))}
          </ul>
        </section>
      </main>

      <footer className="landing-foot">
        An advisory prototype built on fictional CVs. It makes no hiring decisions and ranks
        nobody on protected attributes.
      </footer>
    </div>
  );
}
