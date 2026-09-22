/* Pono — page de validation du système de design.
   Mêmes mécanismes que la maquette de référence : icônes injectées par data-icon,
   cartes rendues depuis des données, puces filtrantes, dialogue, notification.
   Les projets sont ceux de l'atelier, pour éprouver les composants sur du vrai. */

/* ── Icônes ──────────────────────────────────────────────────── */

const ICONES = {
  grid: '<path d="M4 4h6v6H4zM14 4h6v6h-6zM4 14h6v6H4zM14 14h6v6h-6z"/>',
  check: '<path d="M5 12.5 9.5 17 19 7.5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
  panel: '<rect x="3.5" y="4.5" width="17" height="15" rx="2" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M9.5 4.5v15" stroke="currentColor" stroke-width="1.6"/>',
  plus: '<path d="M12 5v14M5 12h14" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  search: '<circle cx="11" cy="11" r="6" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="m15.5 15.5 3.5 3.5" stroke="currentColor" stroke-width="1.8" stroke-linecap="round"/>',
  books: '<path d="M5 5h4v14H5zM11 5h3v14h-3zM16.5 6l3 13" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/>',
  teach: '<path d="M4 18V7a2 2 0 0 1 2-2h5v13H6a2 2 0 0 0-2 2z" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M20 18V7a2 2 0 0 0-2-2h-5v13h5a2 2 0 0 1 2 2z" fill="none" stroke="currentColor" stroke-width="1.6"/>',
  graduate: '<path d="M12 5 3 9l9 4 9-4-9-4z" fill="none" stroke="currentColor" stroke-width="1.6" stroke-linejoin="round"/><path d="M7 11.5V16c0 1.4 2.2 2.5 5 2.5s5-1.1 5-2.5v-4.5" fill="none" stroke="currentColor" stroke-width="1.6"/>',
  agent: '<rect x="4.5" y="7.5" width="15" height="11" rx="3" fill="none" stroke="currentColor" stroke-width="1.6"/><path d="M12 4.5v3" stroke="currentColor" stroke-width="1.6"/><circle cx="9.5" cy="13" r="1.2"/><circle cx="14.5" cy="13" r="1.2"/>',
  more: '<circle cx="6" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="18" cy="12" r="1.5"/>',
  download: '<path d="M12 4v10m0 0 4-4m-4 4-4-4M5 19h14" fill="none" stroke="currentColor" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>',
  chevron: '<path d="m6 9 6 6 6-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>',
  arrow: '<path d="M4 12h15m0 0-5-5m5 5-5 5" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>',
};

function poserIcones(racine = document) {
  racine.querySelectorAll("[data-icon]").forEach((element) => {
    const dessin = ICONES[element.dataset.icon];
    if (!dessin) return;
    element.innerHTML = `<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">${dessin}</svg>`;
  });
}

/* ── Les données de l'atelier ────────────────────────────────── */

const ETATS = {
  pose: "Posé",
  cours: "En cours",
  attention: "Attention",
  panne: "En panne",
  veille: "En veille",
};

const PROJETS = [
  {
    nom: "lectio",
    etat: "cours",
    vedette: true,
    resume: "Preview #12 ouverte par l’agent. Deux migrations additives attendent ta validation.",
    meta: "prod · preview · dev",
    quota: { libelle: "Crédits d’hébergement", valeur: 34, texte: "102 / 300" },
  },
  { nom: "vestio", etat: "pose", meta: "en ligne il y a 3 jours" },
  { nom: "nettio", etat: "pose", meta: "en ligne il y a 9 jours" },
  { nom: "fakti", etat: "veille", meta: "aucun déploiement depuis 2 mois" },
  { nom: "kairos", etat: "pose", meta: "en ligne il y a 5 jours" },
  { nom: "boutiqflow", etat: "attention", meta: "264 / 300 crédits" },
  { nom: "nyatefe", etat: "panne", meta: "migration refusée il y a 5 h" },
  { nom: "barflow", etat: "veille", meta: "en veille depuis 6 semaines" },
  { nom: "firmo", etat: "pose", meta: "en ligne il y a 3 semaines" },
];

const DEPLOIEMENTS = [
  { nom: "lectio · preview #12", etat: "cours", meta: "par l’agent · il y a 12 min" },
  { nom: "nyatefe · production", etat: "panne", meta: "refusé · migration destructrice" },
  { nom: "vestio · production", etat: "pose", meta: "par toi · il y a 3 jours" },
];

/* ── Rendu ───────────────────────────────────────────────────── */

function niveau(valeur) {
  if (valeur >= 90) return "critique";
  if (valeur >= 80) return "attention";
  return "normal";
}

function quotaHtml({ libelle, valeur, texte }) {
  return `
    <div class="quota" data-level="${niveau(valeur)}">
      <div class="quota-head"><span>${libelle}</span><strong>${texte}</strong></div>
      <div class="quota-rail"><div class="quota-bar" style="width:${valeur}%"></div></div>
    </div>`;
}

function pastille(etat) {
  return `<i class="state-dot state-${etat}" title="${ETATS[etat]}"><span></span></i>`;
}

function carteHtml(projet) {
  if (projet.vedette) {
    return `
      <button class="project-card featured" data-project="${projet.nom}">
        <span class="card-title">${pastille(projet.etat)}${projet.nom}</span>
        <p class="description">${projet.resume}</p>
      </button>`;
  }
  return `
    <button class="project-card" data-project="${projet.nom}">
      ${pastille(projet.etat)}
      <span>${projet.nom}<span class="card-meta">${projet.meta}</span></span>
    </button>`;
}

/* Les pages de ce dossier ne portent pas toutes les mêmes blocs : chaque rendu
   vérifie que sa cible existe, pour qu'une page puisse n'en montrer qu'une partie. */
function rendre() {
  const grille = document.getElementById("main-projects");
  const deploiements = document.getElementById("deployments");
  if (!grille || !deploiements) {
    poserIcones();
    return;
  }
  grille.innerHTML = PROJETS.map(carteHtml).join("");
  deploiements.innerHTML = DEPLOIEMENTS.map(
    (ligne) => `
      <button class="project-card" data-project="${ligne.nom}">
        ${pastille(ligne.etat)}
        <span>${ligne.nom}<span class="card-meta">${ligne.meta}</span></span>
      </button>`,
  ).join("");
  poserIcones();
}

/* ── Les puces d'état ────────────────────────────────────────── */

const resultats = document.getElementById("state-results");

function filtrer(etat) {
  if (!resultats) return;
  const liste = PROJETS.filter((projet) => projet.etat === etat);
  document.getElementById("state-title").textContent = `${ETATS[etat]} · ${liste.length} projet${liste.length > 1 ? "s" : ""}`;
  document.getElementById("results").innerHTML = liste.length
    ? liste
        .map(
          (projet) => `
        <button class="project-card" data-project="${projet.nom}">
          ${pastille(projet.etat)}
          <span>${projet.nom}<span class="card-meta">${projet.meta ?? ""}</span></span>
        </button>`,
        )
        .join("")
    : `<p class="description">Aucun projet dans cet état.</p>`;
  resultats.hidden = false;
  poserIcones(resultats);
}

document.querySelectorAll(".chip[data-state]").forEach((puce) => {
  puce.addEventListener("click", () => {
    document.querySelectorAll(".chip[data-state]").forEach((autre) => {
      autre.classList.toggle("active", autre === puce);
      autre.setAttribute("aria-pressed", String(autre === puce));
    });
    filtrer(puce.dataset.state);
  });
});

const menuEtats = document.getElementById("state-menu");
if (menuEtats) {
  menuEtats.innerHTML = `<button data-state="veille">En veille <span>2</span></button>`;
  menuEtats.querySelector("button").addEventListener("click", () => {
    menuEtats.hidden = true;
    filtrer("veille");
  });
  document.getElementById("more-states").addEventListener("click", (evenement) => {
    evenement.stopPropagation();
    menuEtats.hidden = !menuEtats.hidden;
  });
}

/* ── Mettre en ligne : le refus et la validation ─────────────── */

const dialogue = document.getElementById("detail");
const menuDeploiement = document.getElementById("deploy-menu");

const CAS = {
  refus: {
    etat: "panne",
    titre: "nyatefe · mise en ligne refusée",
    corps: `
      <p>La migration <strong>0007_drop_orders.sql</strong> supprime une table qui contient des
      données en production.</p>
      <div class="verdict refus">
        <strong>Ce que le système a bloqué</strong>
        <span>Une suppression de table. Rien n’a été exécuté, la production n’a pas bougé.</span>
      </div>
      <p>Ce refus vient du système, pas de l’agent. Il ne se contourne pas par une instruction.</p>
      <button class="ghost" data-fermer>Voir la migration</button>`,
  },
  accord: {
    etat: "pose",
    titre: "lectio · prêt pour la production",
    corps: `
      <p>Deux migrations additives, aucune suppression. La preview a répondu, aucun secret dans le
      dépôt.</p>
      <div class="verdict accord">
        <strong>Les trois garde-fous sont verts</strong>
        <span>Secrets · preview vérifiée · migrations additives.</span>
      </div>
      <p>Après ta validation, la production est déployée et les migrations rejouées sur la base
      principale.</p>
      <button class="launch" data-fermer data-notifier>Valider et mettre en ligne</button>`,
  },
};

function ouvrirCas(cle) {
  const cas = CAS[cle];
  document.getElementById("detail-content").innerHTML = `
    <div class="card-title">${pastille(cas.etat)}</div>
    <h2>${cas.titre}</h2>
    ${cas.corps}`;
  poserIcones(dialogue);
  dialogue.showModal();
}

if (menuDeploiement && dialogue) {
  document.getElementById("deploy-button").addEventListener("click", (evenement) => {
    evenement.stopPropagation();
    const ouvert = menuDeploiement.hidden;
    menuDeploiement.hidden = !ouvert;
    evenement.currentTarget.setAttribute("aria-expanded", String(ouvert));
  });

  menuDeploiement.querySelectorAll("button").forEach((bouton) => {
    bouton.addEventListener("click", () => {
      menuDeploiement.hidden = true;
      ouvrirCas(bouton.dataset.case);
    });
  });

  dialogue.addEventListener("click", (evenement) => {
    const cible = evenement.target;
    if (!(cible instanceof HTMLElement) || !cible.hasAttribute("data-fermer")) return;
    dialogue.close();
    if (cible.hasAttribute("data-notifier")) notifier("lectio est en ligne · déploiement 6ab2d0d");
  });
}

/* ── Notification ────────────────────────────────────────────── */

const notification = document.getElementById("toast");
let minuterie;

function notifier(message) {
  if (!notification) return;
  notification.textContent = message;
  notification.hidden = false;
  clearTimeout(minuterie);
  minuterie = setTimeout(() => {
    notification.hidden = true;
  }, 4000);
}

/* ── Panneau et actions secondaires ──────────────────────────── */

document.querySelectorAll('[data-action="sidebar"]').forEach((bouton) => {
  bouton.addEventListener("click", () => {
    document.body.classList.toggle("sidebar-collapsed");
  });
});

document.querySelectorAll("[data-project]").forEach((element) => {
  element.addEventListener("click", () => notifier(`${element.dataset.project} · ouvert`));
});

document.getElementById("all-projects")?.addEventListener("click", () => {
  notifier("Neuf projets posés dans l’atelier.");
});

document.addEventListener("click", () => {
  if (menuDeploiement) menuDeploiement.hidden = true;
  if (menuEtats) menuEtats.hidden = true;
});

/* ── Démarrage ───────────────────────────────────────────────── */

rendre();
filtrer("attention");
