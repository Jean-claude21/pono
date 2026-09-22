/* Pono — page de validation du système de design.
   Les données sont fictives mais réalistes : elles viennent des projets de l'atelier,
   pour éprouver les composants sur des cas vrais plutôt que sur du remplissage. */

const PROJETS = [
  {
    nom: "vestio",
    etat: "pose",
    etatTexte: "Posé",
    prod: "vestio.netlify.app",
    preview: null,
    dev: "vestio-dev.coolify.app",
    dernier: "il y a 3 jours · par toi",
    quota: { libelle: "Crédits d'hébergement", valeur: 62, texte: "186 / 300" },
  },
  {
    nom: "lectio",
    etat: "cours",
    etatTexte: "En cours",
    prod: "lectio-reads.netlify.app",
    preview: "deploy-preview-12",
    dev: "lectio-dev.coolify.app",
    dernier: "il y a 12 minutes · par l'agent",
    quota: { libelle: "Crédits d'hébergement", valeur: 34, texte: "102 / 300" },
  },
  {
    nom: "boutiqflow",
    etat: "attention",
    etatTexte: "Attention",
    prod: "boutiqflow.netlify.app",
    preview: null,
    dev: null,
    dernier: "il y a 26 jours",
    quota: { libelle: "Crédits d'hébergement", valeur: 88, texte: "264 / 300" },
  },
  {
    nom: "barflow",
    etat: "veille",
    etatTexte: "En veille",
    prod: "barflow.netlify.app",
    preview: null,
    dev: null,
    dernier: "il y a 2 mois",
    quota: { libelle: "Compute de la base", valeur: 12, texte: "12 / 100 CU-h" },
  },
  {
    nom: "nyatefe",
    etat: "panne",
    etatTexte: "En panne",
    prod: "nyatefe.netlify.app",
    preview: null,
    dev: null,
    dernier: "échec il y a 5 h · migration refusée",
    quota: { libelle: "Crédits d'hébergement", valeur: 97, texte: "291 / 300" },
  },
];

const DEPLOIEMENTS = [
  ["il y a 12 min", "lectio · preview #12", "l'agent", "cours", "En cours"],
  ["il y a 5 h", "nyatefe · production", "toi", "panne", "Refusé"],
  ["il y a 3 j", "vestio · production", "toi", "pose", "En ligne"],
  ["il y a 6 j", "lectio · production", "toi", "pose", "En ligne"],
];

const QUOTAS = [
  { libelle: "Crédits d'hébergement · nyatefe", valeur: 97, texte: "291 / 300" },
  { libelle: "Crédits d'hébergement · boutiqflow", valeur: 88, texte: "264 / 300" },
  { libelle: "Compute de la base · lectio", valeur: 41, texte: "41 / 100 CU-h" },
];

const NUANCES = [
  ["--fond", "Fond"],
  ["--surface", "Surface"],
  ["--surface-creuse", "Surface creuse"],
  ["--ligne", "Ligne"],
  ["--encre", "Encre"],
  ["--encre-douce", "Encre douce"],
  ["--accent", "Accent"],
  ["--pose", "Posé"],
  ["--cours", "En cours"],
  ["--attention", "Attention"],
  ["--panne", "En panne"],
  ["--veille", "En veille"],
];

const ESPACEMENTS = ["--e1", "--e2", "--e3", "--e4", "--e5", "--e6", "--e7", "--e8"];

/* ─────────────── Rendu ─────────────── */

function niveauQuota(valeur) {
  if (valeur >= 90) return "critique";
  if (valeur >= 80) return "attention";
  return "normal";
}

function quotaHtml({ libelle, valeur, texte }) {
  return `
    <div class="quota" data-niveau="${niveauQuota(valeur)}">
      <div class="quota__tete"><span>${libelle}</span><strong>${texte}</strong></div>
      <div class="quota__rail"><div class="quota__jauge" style="width:${valeur}%"></div></div>
    </div>`;
}

function lienEnv(libelle, cible) {
  if (!cible) return `<span class="lien-env" data-muet>${libelle} · absent</span>`;
  return `<a class="lien-env" href="#" title="${cible}">${libelle}</a>`;
}

function carteHtml(projet) {
  return `
    <article class="carte">
      <div class="carte__tete">
        <span class="carte__nom">${projet.nom}</span>
        <span class="etat etat--${projet.etat}">${projet.etatTexte}</span>
      </div>
      <div class="carte__liens">
        ${lienEnv("prod", projet.prod)}
        ${lienEnv("preview", projet.preview)}
        ${lienEnv("dev", projet.dev)}
      </div>
      ${quotaHtml(projet.quota)}
      <div class="carte__pied">
        <span>${projet.dernier}</span>
        <button class="bouton bouton--fantome">Ouvrir</button>
      </div>
    </article>`;
}

function rendre() {
  document.getElementById("projets").innerHTML = PROJETS.map(carteHtml).join("");

  document.getElementById("deploiements").innerHTML = DEPLOIEMENTS.map(
    ([quand, quoi, qui, etat, texte]) => `
      <div class="liste__ligne">
        <span class="faible">${quand}</span>
        <span>${quoi}</span>
        <span class="faible">${qui}</span>
        <span class="etat etat--${etat}">${texte}</span>
      </div>`,
  ).join("");

  document.getElementById("quotas").innerHTML = QUOTAS.map(quotaHtml).join("");

  document.getElementById("nuancier").innerHTML = NUANCES.map(
    ([jeton, nom]) => `
      <div class="nuance">
        <div class="nuance__pastille" style="background: var(${jeton})"></div>
        <span>${nom}</span>
        <span class="faible mono">${jeton}</span>
      </div>`,
  ).join("");

  document.getElementById("espacement").innerHTML = ESPACEMENTS.map(
    (jeton) => `
      <div class="nuance">
        <div style="width: var(${jeton}); height: 44px; background: var(--accent); border-radius: 2px"></div>
        <span class="faible mono">${jeton}</span>
      </div>`,
  ).join("");
}

/* ─────────────── Le thème ─────────────── */

const bascule = document.getElementById("bascule-theme");

function appliquerTheme(theme) {
  document.documentElement.dataset.theme = theme;
  bascule.textContent = theme === "sombre" ? "Mode clair" : "Mode sombre";
  bascule.setAttribute("aria-pressed", String(theme === "sombre"));
  try {
    localStorage.setItem("pono-theme", theme);
  } catch {
    /* Un navigateur privé refuse le stockage : le thème reste valable pour la session. */
  }
}

bascule.addEventListener("click", () => {
  appliquerTheme(document.documentElement.dataset.theme === "sombre" ? "clair" : "sombre");
});

/* ─────────────── Le dialogue de mise en ligne ─────────────── */

const dialogue = document.getElementById("dialogue");

const CAS = {
  refus: {
    etat: "panne",
    etatTexte: "Refusé",
    titre: "La mise en ligne est refusée",
    corps: `
      <p>La migration <span class="mono">0007_drop_orders.sql</span> supprime une table qui contient
      des données en production.</p>
      <div class="verdict verdict--refus">
        <strong>Ce que le système a bloqué</strong>
        <span>Une suppression de table. Rien n'a été exécuté, la production n'a pas bougé.</span>
      </div>
      <p class="faible">Ce refus vient du système, pas de l'agent. Il ne se contourne pas par une
      instruction.</p>`,
    actions: `
      <button class="bouton bouton--fantome" data-fermer>Fermer</button>
      <button class="bouton bouton--contour" data-fermer>Voir la migration</button>`,
  },
  accord: {
    etat: "pose",
    etatTexte: "Prêt",
    titre: "Mettre lectio en ligne",
    corps: `
      <p>Deux migrations additives, aucune suppression. La preview a répondu, les secrets sont
      absents du dépôt.</p>
      <div class="verdict verdict--accord">
        <strong>Les trois garde-fous sont verts</strong>
        <span>Secrets · preview vérifiée · migrations additives.</span>
      </div>
      <p class="faible">Après ta validation, la production est déployée et la migration rejouée sur
      la base principale.</p>`,
    actions: `
      <button class="bouton bouton--fantome" data-fermer>Annuler</button>
      <button class="bouton bouton--premier" data-fermer data-notifier>Valider et mettre en ligne</button>`,
  },
};

document.querySelectorAll("[data-ouvrir-dialogue]").forEach((bouton) => {
  bouton.addEventListener("click", () => {
    const cas = CAS[bouton.dataset.ouvrirDialogue];
    const badge = document.getElementById("dialogue-etat");
    badge.className = `etat etat--${cas.etat}`;
    badge.textContent = cas.etatTexte;
    document.getElementById("dialogue-titre").textContent = cas.titre;
    document.getElementById("dialogue-corps").innerHTML = cas.corps;
    document.getElementById("dialogue-actions").innerHTML = cas.actions;
    dialogue.showModal();
  });
});

dialogue.addEventListener("click", (evenement) => {
  const cible = evenement.target;
  if (!(cible instanceof HTMLElement) || !cible.hasAttribute("data-fermer")) return;
  dialogue.close();
  if (cible.hasAttribute("data-notifier")) notifier("lectio est en ligne. Déploiement 6ab2d0d.");
});

/* ─────────────── La notification ─────────────── */

const notification = document.getElementById("notification");
let minuterie;

function notifier(message) {
  notification.innerHTML = `<span class="etat etat--pose">Fait</span><span>${message}</span>`;
  notification.hidden = false;
  clearTimeout(minuterie);
  minuterie = setTimeout(() => {
    notification.hidden = true;
  }, 4000);
}

document.getElementById("voir-notification").addEventListener("click", () => {
  notifier("nyatefe : il te reste 9 crédits d'hébergement ce mois-ci.");
});

/* ─────────────── Démarrage ─────────────── */

let themeInitial = "clair";
try {
  themeInitial = localStorage.getItem("pono-theme") ?? "clair";
} catch {
  /* Stockage indisponible : on démarre en clair. */
}
appliquerTheme(themeInitial);
rendre();
