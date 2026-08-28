# Ground Truth — Sample CV Dataset

Reference facts for evaluating extraction, retrieval and matching. Source of truth
is `data/sample_cvs/*.txt`. Canonical entity names are the post-normalization forms.

## Deliberate dataset design

- **Python holders (5):** Alice Perera, David Silva, Priya Raj, Kevin Wong, Ravi Kumar
- **AWS holders (5):** Alice Perera ("Amazon Web Services"), David Silva ("AWS"),
  Michael Jayawardena ("Amazon Web Services"), Priya Raj ("AWS"), Ravi Kumar ("Amazon Web Services")
- **Python + AWS + AI (strong):** Alice Perera, Priya Raj
- **Python + AWS, weak AI:** David Silva ("Basic Machine Learning" only) — supports the
  "Why Alice over David?" explainability query
- **Shared projects (graph paths):**
  - Customer Support AI — Alice Perera, Priya Raj
  - Retail Analytics Dashboard — Sarah Fernando, Kevin Wong
  - Cloud Migration Initiative — Michael Jayawardena, Ravi Kumar
- **Shared employers:** Nexlify Solutions (Alice, Priya), Lanka Retail Tech (David,
  Sarah, Kevin), CloudReach Lanka (Michael, Ravi), InsightWorks (Priya, Ravi)

## Normalization traps (surface form → canonical)

| Surface form in CV | Canonical | Appears in |
|---|---|---|
| Amazon Web Services | AWS | Alice, Michael, Ravi |
| Natural Language Processing | NLP | Alice, Priya |
| ReactJS | React | Sarah, Kevin |
| Application Programming Interface design | API design | Kevin (cf. Alice "REST API design", David "API design") |
| JavaScript / JS | JavaScript | Sarah, Kevin |

## Per-person canonical summary

| Person | Role | Key skills | Technologies | Projects | Domains |
|---|---|---|---|---|---|
| Alice Perera | Senior AI Engineer | Python, ML, NLP, AWS, Prompt Engineering, API design | FastAPI, Docker, LangChain, PyTorch, PostgreSQL | Customer Support AI, Document Intelligence Platform | AI, Backend Development |
| David Silva | Backend Engineer | Python, AWS, API design, Databases, Microservices, ML (basic) | FastAPI, PostgreSQL, Redis, Docker, RabbitMQ | Payment Gateway Platform, Inventory Management System | Backend Development, FinTech |
| Sarah Fernando | Frontend Engineer | React, TypeScript, JavaScript, Accessibility | Next.js, Tailwind CSS, Vite, Figma, Jest | Retail Analytics Dashboard, Corporate Website Revamp | Frontend Development, UX |
| Michael Jayawardena | DevOps Engineer | AWS, IaC, CI/CD, Containers, Linux | Terraform, Docker, Kubernetes, GitHub Actions, Prometheus, Grafana | Cloud Migration Initiative, CI/CD Modernisation | DevOps, Cloud Infrastructure |
| Priya Raj | Data Scientist | Python, ML, NLP, Statistics, AWS | TensorFlow, Pandas, scikit-learn, SQL, Jupyter, Docker | Customer Support AI, Churn Prediction Model | AI, Data Science |
| Kevin Wong | Full-Stack Developer | JavaScript, Python, React, Node.js, API design | Express, MongoDB, Flask, Docker | Retail Analytics Dashboard, Booking Platform | Full-Stack, Web |
| Ravi Kumar | Data Engineer | Python, SQL, AWS, Data Warehousing | Apache Spark, Apache Airflow, Snowflake, Docker, dbt | Enterprise Data Lake, Cloud Migration Initiative | Data Engineering, Cloud Infrastructure |

## Expected answers for the spec's example queries

1. **Who has Python experience?** → Alice, David, Priya, Kevin, Ravi
2. **Who has both Python and AWS?** → Alice, David, Priya, Ravi
3. **Which employees have AI experience?** → Alice, Priya (strong); David (basic only)
4. **How is Alice connected to NLP?** → direct HAS_SKILL edge; also via Customer
   Support AI ↔ Priya (both NLP)
5. **Who suits a Python + AWS AI project?** → Alice (strongest), Priya; David weaker
6. **Three-person team: Python, AWS, React** → e.g. Alice/Priya (Python+AWS) +
   Sarah or Kevin (React); Kevin covers Python+React
7. **Missing skills for such a project** → depends on picks; if Alice+Priya+Sarah,
   nothing missing; if only backend picks, React missing
8. **Why Alice over David?** → Alice: ML/NLP skills + Customer Support AI project
   evidence; David: only basic ML, no AI project
9. **Technologies connected to Alice's projects** → Customer Support AI: LangChain,
   FastAPI, AWS, Python; Document Intelligence Platform: PyTorch, Docker, Python
10. **People with overlapping skills** → Alice↔Priya (Python, ML, NLP, AWS);
    Sarah↔Kevin (React, JavaScript); Michael↔Ravi (AWS, Docker); Alice↔David
    (Python, AWS, FastAPI, API design)
