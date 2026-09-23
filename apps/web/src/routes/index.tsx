import { createFileRoute } from "@tanstack/react-router";
import * as m from "@/paraglide/messages.js";
import { errorMessage } from "@/lib/i18n";

type LandingSearch = { error?: string };

export const Route = createFileRoute("/")({
  validateSearch: (search: Record<string, unknown>): LandingSearch => ({
    error: typeof search.error === "string" ? search.error : undefined,
  }),
  component: Landing,
});

type ProjectState = "healthy" | "active" | "warning" | "failing" | "idle";

const narrowTracking = { letterSpacing: "0.08em" };

// Access is on request while Pono is being built: one action, one question.
function accessRequestUrl(): string {
  const subject = encodeURIComponent(m.access_request_subject());
  const body = encodeURIComponent(`${m.access_request_body()}\n\n`);
  return `mailto:messanjeanclaude@gmail.com?subject=${subject}&body=${body}`;
}

function Landing() {
  const { error } = Route.useSearch();
  const accessUrl = accessRequestUrl();
  return (
    <>
      <header className="site-header">
        <a className="monogram" href="/">
          <b>P</b>Pono
        </a>
        <a className="btn btn-ghost btn-sm" href={accessUrl}>
          {m.access_request_cta()}
        </a>
      </header>

      {error ? (
        <div className="wrap" style={{ paddingTop: 24 }}>
          <div className="verdict" role="alert">
            <p>{errorMessage(error)}</p>
          </div>
        </div>
      ) : null}

      <main>
        <Hero accessUrl={accessUrl} />
        <Problem />
        <Benefits />
        <Mechanism />
        <Faq />

        <section className="cta-band">
          <div className="wrap">
            <div>
              <h2>{m.cta_title()}</h2>
              <p>{m.cta_body()}</p>
            </div>
            <a className="btn btn-primary" href={accessUrl}>
              {m.access_request_cta()}
            </a>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="wrap">
          <span className="monogram" style={{ fontSize: 16 }}>
            <b style={{ width: 22, height: 22, fontSize: 12 }}>P</b>
            {m.footer_signature()}
          </span>
          <span className="mono-label">Pono · 2026</span>
        </div>
      </footer>
    </>
  );
}

function Hero({ accessUrl }: Readonly<{ accessUrl: string }>) {
  return (
    <section className="hero">
      <div className="wrap">
        <div>
          <p className="mono-label">{m.hero_eyebrow()}</p>
          <h1 style={{ marginTop: 20 }}>
            {m.hero_title_lead()} <span>{m.hero_title_rest()}</span>
          </h1>
          <p className="lede">{m.hero_lede()}</p>
          <div className="actions">
            <a className="btn btn-primary" href={accessUrl}>
              {m.access_request_cta()}
            </a>
            <a className="btn btn-ghost" href="#mechanism">
              {m.hero_how_it_works()}
            </a>
          </div>
          <p className="fine">
            <b>{m.hero_fine_strong()}</b> {m.hero_fine_rest()}
          </p>
        </div>

        {/* The proof sits in the first screen: the workshop, and the moment that matters. */}
        <figure className="proof" style={{ margin: 0 }}>
          <div className="proof-head">
            <span className="mono-label">{m.proof_workshop()}</span>
            <span className="mono-label">{m.proof_projects_count({ count: 6 })}</span>
          </div>
          <ProofRow
            name="lectio"
            state="active"
            detail={m.proof_detail_preview({ number: 12 })}
            usage="102/300"
          />
          <ProofRow name="vestio" state="healthy" detail={m.proof_detail_online()} usage="186/300" />
          <ProofRow
            name="boutiqflow"
            state="warning"
            detail={m.proof_detail_quota_low()}
            usage="264/300"
            nearLimit
          />
          <div className="verdict">
            <span className="mono-label">{m.proof_refused_label({ project: "nyatefe" })}</span>
            <h3>{m.proof_refused_title()}</h3>
            <p>{m.proof_refused_body()}</p>
          </div>
          <figcaption className="proof-caption">
            <span className="mono-label" style={narrowTracking}>
              {m.proof_caption()}
            </span>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

function ProofRow({
  name,
  state,
  detail,
  usage,
  nearLimit = false,
}: Readonly<{
  name: string;
  state: ProjectState;
  detail: string;
  usage: string;
  nearLimit?: boolean;
}>) {
  return (
    <div className="proof-row">
      <span className={`state state-${state}`}>{name}</span>
      <span className="mono-label" style={narrowTracking}>
        {detail}
      </span>
      <span className="figures" style={nearLimit ? { color: "var(--warning)" } : undefined}>
        {usage}
      </span>
    </div>
  );
}

function Problem() {
  const questions = [m.problem_q1(), m.problem_q2(), m.problem_q3()];
  return (
    <section className="section">
      <div className="wrap">
        <p className="mono-label">{m.problem_label()}</p>
        <h2 style={{ marginTop: 14 }}>{m.problem_title()}</h2>
        <div className="questions">
          {questions.map((question, index) => (
            <p className="question" key={question}>
              <span className="mono-label">{String(index + 1).padStart(2, "0")}</span>
              {question}
            </p>
          ))}
        </div>
      </div>
    </section>
  );
}

function Benefits() {
  const cells = [
    { label: m.benefit_state_label(), title: m.benefit_state_title(), body: m.benefit_state_body() },
    {
      label: m.benefit_guardrails_label(),
      title: m.benefit_guardrails_title(),
      body: m.benefit_guardrails_body(),
    },
    { label: m.benefit_quotas_label(), title: m.benefit_quotas_title(), body: m.benefit_quotas_body() },
  ];
  return (
    <section className="section alt">
      <div className="wrap">
        <p className="mono-label">{m.benefits_label()}</p>
        <h2 style={{ marginTop: 14 }}>{m.benefits_title()}</h2>
        <div className="grid-3">
          {cells.map((cell) => (
            <div className="cell" key={cell.label}>
              <span className="mono-label">{cell.label}</span>
              <h3>{cell.title}</h3>
              <p>{cell.body}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Mechanism() {
  const limits = [m.limit_not_editor(), m.limit_single_path(), m.limit_no_ai_resale()];
  return (
    <section className="section" id="mechanism">
      <div className="wrap split">
        <div>
          <p className="mono-label">{m.mechanism_label()}</p>
          <h2 style={{ marginTop: 14 }}>{m.mechanism_title()}</h2>
          <p className="intro">{m.mechanism_intro()}</p>
        </div>
        <div>
          <div className="verdict healthy">
            <span className="mono-label">{m.mechanism_ready_label({ project: "lectio" })}</span>
            <h3>{m.mechanism_ready_title()}</h3>
            <p>{m.mechanism_ready_body()}</p>
          </div>
          <div className="limits">
            {limits.map((limit) => (
              <p className="limit" key={limit}>
                <span className="mono-label">—</span>
                {limit}
              </p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Faq() {
  const entries = [
    { question: m.faq_for_me_question(), answer: m.faq_for_me_answer() },
    { question: m.faq_if_pono_stops_question(), answer: m.faq_if_pono_stops_answer() },
    { question: m.faq_why_not_replit_question(), answer: m.faq_why_not_replit_answer() },
    { question: m.faq_price_question(), answer: m.faq_price_answer() },
  ];
  return (
    <section className="section">
      <div className="wrap split">
        <div>
          <p className="mono-label">{m.faq_label()}</p>
          <h2 style={{ marginTop: 14 }}>{m.faq_title()}</h2>
        </div>
        <dl className="faq" style={{ margin: 0 }}>
          {entries.map((entry) => (
            <div key={entry.question}>
              <dt>{entry.question}</dt>
              <dd>{entry.answer}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
