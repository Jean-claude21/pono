import type { ReactNode } from "react";
import { createFileRoute } from "@tanstack/react-router";

export const Route = createFileRoute("/")({
  component: Landing,
});

const CONTACT =
  "mailto:messanjeanclaude@gmail.com?subject=Acc%C3%A8s%20Pono&body=Quel%20projet%20veux-tu%20poser%20en%20premier%20%3F%0A%0A";

function Landing() {
  return (
    <main className="mx-auto max-w-3xl px-6 py-20 sm:py-28">
      <Hero />
      <Probleme />
      <Resultat />
      <Mecanisme />
      <Demonstration />
      <Limites />
      <Objections />
      <Action />
      <Pied />
    </main>
  );
}

function Hero() {
  return (
    <header>
      <p className="text-sm font-medium tracking-widest text-stone-500 uppercase">Pono</p>
      <h1 className="mt-6 text-4xl leading-tight font-semibold text-balance sm:text-5xl">
        Construis depuis Claude. Ton app démarre à 0 €, elle tient, et elle est à toi.
      </h1>
      <p className="mt-6 text-lg text-stone-600">
        Le poste de contrôle de tes projets construits par agent : leur état réel au même endroit,
        et des garde-fous que ton agent ne peut pas contourner.
      </p>
      <p className="mt-6 inline-block rounded-full border border-stone-300 px-3 py-1 text-sm text-stone-600">
        En construction · accès sur demande
      </p>
    </header>
  );
}

function Section({
  titre,
  children,
}: Readonly<{ titre: string; children: ReactNode }>) {
  return (
    <section className="mt-16 border-t border-stone-200 pt-10">
      <h2 className="text-xl font-semibold">{titre}</h2>
      <div className="mt-4 space-y-4 text-stone-700">{children}</div>
    </section>
  );
}

function Probleme() {
  return (
    <Section titre="Trois questions">
      <ul className="space-y-2">
        <li>Tu as plusieurs projets en ligne. Lequel tourne encore ?</li>
        <li>Quelle base est branchée sur lequel ?</li>
        <li>Qui a déployé en dernier, et qu'est-ce qui est parti ?</li>
      </ul>
      <p>
        Si tu dois chercher pour répondre, tes projets ne sont pas tenus. Ils sont simplement
        éparpillés.
      </p>
    </Section>
  );
}

function Resultat() {
  return (
    <Section titre="Ce que tu obtiens">
      <p>
        Un atelier où chaque projet est posé : son état, ses environnements, ses déploiements, sa
        base, ses quotas. Tu reprends un projet sans rien chercher.
      </p>
    </Section>
  );
}

function Mecanisme() {
  const lignes = [
    ["Ton agent écrit.", "Claude, Codex ou ChatGPT, celui que tu paies déjà."],
    ["Pono tient l'état et les règles.", "Rien ne part en production sans ta validation."],
    ["Ton code reste chez toi.", "Ton GitHub, ta base, ton hébergement."],
  ];
  return (
    <Section titre="Comment ça marche">
      <dl className="space-y-4">
        {lignes.map(([titre, detail]) => (
          <div key={titre}>
            <dt className="font-medium text-stone-900">{titre}</dt>
            <dd className="text-stone-600">{detail}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

function Demonstration() {
  return (
    <Section titre="La démonstration">
      <p>
        Elle sera publiée quand elle sera réelle : un projet, du début à la fin, sans accélération.
        On y verra la mise en ligne <strong>refusée</strong> tant qu'un humain n'a pas validé, puis
        acceptée.
      </p>
      <p className="text-sm text-stone-500">
        Aucune image de synthèse, aucun chiffre non mesuré. Ce qui n'est pas encore prouvé n'est pas
        encore affiché.
      </p>
    </Section>
  );
}

function Limites() {
  return (
    <Section titre="Ce que Pono ne fait pas">
      <ul className="list-disc space-y-2 pl-5">
        <li>Ce n'est pas un éditeur de code : tu restes dans ton agent.</li>
        <li>Un seul chemin technique pour l'instant, pas encore tous les fournisseurs.</li>
        <li>Pas d'application mobile.</li>
        <li>Pas d'intelligence artificielle revendue au compteur. Tu paies ton agent, une fois.</li>
      </ul>
    </Section>
  );
}

function Objections() {
  const questions = [
    ["Est-ce pour moi ?", "Si tu construis déjà avec un agent et que tes projets s'éparpillent, oui."],
    ["Est-ce vrai ?", "Le chemin complet et le verrou de production ont été éprouvés sur de vrais projets."],
    ["Combien de temps pour démarrer ?", "Le temps de connecter tes comptes. On te dit lesquels créer, et on vérifie."],
    ["Et si ça ne marche pas ?", "Tes projets continuent de tourner : ils sont chez toi, pas chez nous."],
    ["Pourquoi pas Replit ?", "Replit fabrique vite, et bien. Pono tient ce qui est fabriqué, et ne le retient pas."],
    ["Combien ça coûte ?", "Prix fixe, jamais de crédits. Les paliers gratuits de tes fournisseurs suffisent pour démarrer."],
  ];
  return (
    <Section titre="Les questions qu'on se pose">
      <dl className="space-y-4">
        {questions.map(([q, r]) => (
          <div key={q}>
            <dt className="font-medium text-stone-900">{q}</dt>
            <dd className="text-stone-600">{r}</dd>
          </div>
        ))}
      </dl>
    </Section>
  );
}

function Action() {
  return (
    <section className="mt-16 rounded-2xl bg-stone-900 px-8 py-10 text-stone-100">
      <h2 className="text-xl font-semibold">Demander un accès</h2>
      <p className="mt-3 text-stone-300">
        Dis-nous simplement une chose : <strong>quel projet veux-tu poser en premier ?</strong>
      </p>
      <a
        className="mt-6 inline-block rounded-lg bg-stone-100 px-5 py-3 font-medium text-stone-900 transition hover:bg-white"
        href={CONTACT}
      >
        Demander un accès
      </a>
    </section>
  );
}

function Pied() {
  return (
    <footer className="mt-16 border-t border-stone-200 pt-8 text-sm text-stone-500">
      <p className="text-base font-medium text-stone-900">Pose. Ça tient.</p>
      <p className="mt-2">Pono — poste de contrôle des projets construits par agent.</p>
    </footer>
  );
}
