import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: Landing,
});

// Accès sur demande pendant la construction : une seule action, une seule question.
const DEMANDE =
  "mailto:messanjeanclaude@gmail.com?subject=Acc%C3%A8s%20Pono&body=Quel%20projet%20veux-tu%20poser%20en%20premier%20%3F%0A%0A";

const espacement = { letterSpacing: "0.08em" };

function Landing() {
  return (
    <>
      <header className="site-header">
        <a className="monogram" href="/">
          <b>P</b>Pono
        </a>
        <a className="btn btn-ghost btn-sm" href={DEMANDE}>
          Demander un accès
        </a>
      </header>

      <main>
        <Hero />
        <Probleme />
        <Obtenir />
        <Mecanisme />
        <Questions />

        <section className="cta-band">
          <div className="wrap">
            <div>
              <h2>Quel projet veux-tu poser en premier&nbsp;?</h2>
              <p>Accès sur demande, pendant la construction.</p>
            </div>
            <a className="btn btn-primary" href={DEMANDE}>
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
            <a className="btn btn-primary" href={DEMANDE}>
              Demander un accès
            </a>
            <a className="btn btn-ghost" href="#mecanisme">
              Comment ça marche
            </a>
          </div>
          <p className="fine">
            <b>Démarre à 0 €</b> avec les paliers gratuits de tes fournisseurs. Aucun crédit d’IA.
          </p>
        </div>

        {/* La preuve dans le premier écran : l'atelier, et le moment qui compte. */}
        <figure className="proof" style={{ margin: 0 }}>
          <div className="proof-head">
            <span className="mono-label">Atelier</span>
            <span className="mono-label">6 projets</span>
          </div>
          <Ligne nom="lectio" etat="cours" detail="preview #12" quota="102/300" />
          <Ligne nom="vestio" etat="pose" detail="en ligne" quota="186/300" />
          <Ligne nom="boutiqflow" etat="attention" detail="quota bas" quota="264/300" alerte />
          <div className="verdict">
            <span className="mono-label">Mise en ligne refusée · nyatefe</span>
            <h3>Une migration supprime une table en production.</h3>
            <p>Rien n’a été exécuté. Ce refus vient du système, pas de l’agent.</p>
          </div>
          <figcaption className="proof-caption">
            <span className="mono-label" style={espacement}>
              maquette · données de l’atelier
            </span>
          </figcaption>
        </figure>
      </div>
    </section>
  );
}

function Ligne({
  nom,
  etat,
  detail,
  quota,
  alerte = false,
}: Readonly<{ nom: string; etat: string; detail: string; quota: string; alerte?: boolean }>) {
  return (
    <div className="proof-row">
      <span className={`state state-${etat}`}>{nom}</span>
      <span className="mono-label" style={espacement}>
        {detail}
      </span>
      <span className="figures" style={alerte ? { color: "var(--attention)" } : undefined}>
        {quota}
      </span>
    </div>
  );
}

function Probleme() {
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

function Obtenir() {
  const cellules = [
    [
      "État",
      "Chaque projet, tel qu’il est",
      "Environnements, dernier déploiement, liens qui marchent. Lu chez tes fournisseurs, jamais saisi à la main.",
    ],
    [
      "Garde-fous",
      "La production ne se casse pas",
      "Rien ne part sans ta validation. Le refus est mécanique : ton agent ne peut pas l’argumenter.",
    ],
    [
      "Quotas",
      "Prévenu avant la pause",
      "Tes paliers gratuits surveillés. L’alerte arrive avant que ton site ne s’arrête.",
    ],
  ];
  return (
    <section className="section alt">
      <div className="wrap">
        <p className="mono-label">Ce que tu obtiens</p>
        <h2 style={{ marginTop: 14 }}>L’état réel, les garde-fous, et tes quotas, au même endroit.</h2>
        <div className="grid-3">
          {cellules.map(([etiquette, titre, texte]) => (
            <div className="cell" key={etiquette}>
              <span className="mono-label">{etiquette}</span>
              <h3>{titre}</h3>
              <p>{texte}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function Mecanisme() {
  const limites = [
    "Ce n’est pas un éditeur de code : tu restes dans ton agent.",
    "Un seul chemin technique pour l’instant.",
    "Pas d’IA revendue au compteur.",
  ];
  return (
    <section className="section" id="mecanisme">
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
          <div className="verdict pose">
            <span className="mono-label">Prêt pour la production · lectio</span>
            <h3>Trois garde-fous sont verts.</h3>
            <p>
              Aucun secret dans le dépôt · preview vérifiée · migrations additives. Il ne manque que
              ta validation.
            </p>
          </div>
          <div className="limits">
            {limites.map((limite) => (
              <p className="limit" key={limite}>
                <span className="mono-label">—</span>
                {limite}
              </p>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

function Questions() {
  const questions = [
    ["Est-ce pour moi ?", "Si tu construis déjà avec un agent et que tes projets s’éparpillent, oui."],
    ["Et si Pono s’arrête ?", "Tes projets continuent de tourner : ils sont sur tes comptes, pas les nôtres."],
    ["Pourquoi pas Replit ?", "Replit fabrique vite, et bien. Pono tient ce qui est fabriqué, et ne le retient pas."],
    ["Combien ça coûte ?", "Prix fixe, jamais de crédits. Les paliers gratuits suffisent pour démarrer."],
  ];
  return (
    <section className="section">
      <div className="wrap split">
        <div>
          <p className="mono-label">Questions</p>
          <h2 style={{ marginTop: 14 }}>Ce qu’on se demande avant de poser un projet.</h2>
        </div>
        <dl className="faq" style={{ margin: 0 }}>
          {questions.map(([question, reponse]) => (
            <div key={question}>
              <dt>{question}</dt>
              <dd>{reponse}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
