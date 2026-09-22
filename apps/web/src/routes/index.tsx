import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: Landing,
});

// Access is on request while Pono is being built: one action, one question.
// The copy below is French until phase 1 moves every string into the i18n catalogs.
const ACCESS_REQUEST_URL =
  "mailto:messanjeanclaude@gmail.com?subject=Acc%C3%A8s%20Pono&body=Quel%20projet%20veux-tu%20poser%20en%20premier%20%3F%0A%0A";

const narrowTracking = { letterSpacing: "0.08em" };

type ProjectState = "healthy" | "active" | "warning" | "failing" | "idle";

function Landing() {
  return (
    <>
      <header className="site-header">
        <a className="monogram" href="/">
          <b>P</b>Pono
        </a>
        <a className="btn btn-ghost btn-sm" href={ACCESS_REQUEST_URL}>
          Demander un accès
        </a>
      </header>

      <main>
        <Hero />
        <Problem />
        <Benefits />
        <Mechanism />
        <Faq />

        <section className="cta-band">
          <div className="wrap">
            <div>
              <h2>Quel projet veux-tu poser en premier&nbsp;?</h2>
              <p>Accès sur demande, pendant la construction.</p>
            </div>
            <a className="btn btn-primary" href={ACCESS_REQUEST_URL}>
              Demander un accès
            </a>
          </div>
        </section>
      </main>

      <footer className="site-footer">
        <div className="wrap">
          <span className="monogram" style={{ fontSize: 16 }}>
            <b style={{ width: 22, height: 22, fontSize: 12 }}>P</b>Pose. Ça tient.
          </span>
          <span className="mono-label">Pono · 2026</span>
        </div>
      </footer>
    </>
  );
}

function Hero() {
  return (
    <section className="hero">
      <div className="wrap">
        <div>
          <p className="mono-label">Poste de contrôle des projets construits par agent</p>
          <h1 style={{ marginTop: 20 }}>
            Construis depuis Claude. <span>Ton app tient, et elle est à toi.</span>
          </h1>
          <p className="lede">
            Ton agent écrit le code. Pono tient l’état réel de chaque projet et refuse ce qui casse la
            production. Ton dépôt, ta base et ton hébergement restent à ton nom.
          </p>
          <div className="actions">
            <a className="btn btn-primary" href={ACCESS_REQUEST_URL}>
              Demander un accès
            </a>
            <a className="btn btn-ghost" href="#mechanism">
              Comment ça marche
            </a>
          </div>
          <p className="fine">
            <b>Démarre à 0 €</b> avec les paliers gratuits de tes fournisseurs. Aucun crédit d’IA.
          </p>
        </div>

        {/* The proof sits in the first screen: the workshop, and the moment that matters. */}
        <figure className="proof" style={{ margin: 0 }}>
          <div className="proof-head">
            <span className="mono-label">Atelier</span>
            <span className="mono-label">6 projets</span>
          </div>
          <ProofRow name="lectio" state="active" detail="preview #12" usage="102/300" />
          <ProofRow name="vestio" state="healthy" detail="en ligne" usage="186/300" />
          <ProofRow name="boutiqflow" state="warning" detail="quota bas" usage="264/300" nearLimit />
          <div className="verdict">
            <span className="mono-label">Mise en ligne refusée · nyatefe</span>
            <h3>Une migration supprime une table en production.</h3>
            <p>Rien n’a été exécuté. Ce refus vient du système, pas de l’agent.</p>
          </div>
          <figcaption className="proof-caption">
            <span className="mono-label" style={narrowTracking}>
              maquette · données de l’atelier
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
}: Readonly<{ name: string; state: ProjectState; detail: string; usage: string; nearLimit?: boolean }>) {
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
  const questions = [
    "Tu as plusieurs projets en ligne. Lequel tourne encore ?",
    "Quelle base est branchée sur lequel ?",
    "Qui a déployé en dernier, et qu’est-ce qui est parti ?",
  ];
  return (
    <section className="section">
      <div className="wrap">
        <p className="mono-label">Le problème</p>
        <h2 style={{ marginTop: 14 }}>
          Si tu dois chercher pour répondre, tes projets ne sont pas tenus.
        </h2>
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
    {
      label: "État",
      title: "Chaque projet, tel qu’il est",
      body: "Environnements, dernier déploiement, liens qui marchent. Lu chez tes fournisseurs, jamais saisi à la main.",
    },
    {
      label: "Garde-fous",
      title: "La production ne se casse pas",
      body: "Rien ne part sans ta validation. Le refus est mécanique : ton agent ne peut pas l’argumenter.",
    },
    {
      label: "Quotas",
      title: "Prévenu avant la pause",
      body: "Tes paliers gratuits surveillés. L’alerte arrive avant que ton site ne s’arrête.",
    },
  ];
  return (
    <section className="section alt">
      <div className="wrap">
        <p className="mono-label">Ce que tu obtiens</p>
        <h2 style={{ marginTop: 14 }}>L’état réel, les garde-fous, et tes quotas, au même endroit.</h2>
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
  const limits = [
    "Ce n’est pas un éditeur de code : tu restes dans ton agent.",
    "Un seul chemin technique pour l’instant.",
    "Pas d’IA revendue au compteur.",
  ];
  return (
    <section className="section" id="mechanism">
      <div className="wrap split">
        <div>
          <p className="mono-label">Le mécanisme</p>
          <h2 style={{ marginTop: 14 }}>Ton agent écrit. Pono tient. Tout reste chez toi.</h2>
          <p className="intro">
            Tu restes dans Claude, Codex ou ChatGPT — celui que tu paies déjà. Pono ne revend pas
            d’intelligence : il tient l’état et les règles.
          </p>
        </div>
        <div>
          <div className="verdict healthy">
            <span className="mono-label">Prêt pour la production · lectio</span>
            <h3>Trois garde-fous sont verts.</h3>
            <p>
              Aucun secret dans le dépôt · preview vérifiée · migrations additives. Il ne manque que
              ta validation.
            </p>
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
    { question: "Est-ce pour moi ?", answer: "Si tu construis déjà avec un agent et que tes projets s’éparpillent, oui." },
    { question: "Et si Pono s’arrête ?", answer: "Tes projets continuent de tourner : ils sont sur tes comptes, pas les nôtres." },
    { question: "Pourquoi pas Replit ?", answer: "Replit fabrique vite, et bien. Pono tient ce qui est fabriqué, et ne le retient pas." },
    { question: "Combien ça coûte ?", answer: "Prix fixe, jamais de crédits. Les paliers gratuits suffisent pour démarrer." },
  ];
  return (
    <section className="section">
      <div className="wrap split">
        <div>
          <p className="mono-label">Questions</p>
          <h2 style={{ marginTop: 14 }}>Ce qu’on se demande avant de poser un projet.</h2>
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
