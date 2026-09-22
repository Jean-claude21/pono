# Pono

> **Pose. Ça tient.**

Le poste de contrôle des projets construits par agent. Tu construis depuis Claude ou Codex : ton
app démarre à 0 €, elle tient, et elle est à toi.

## Le mandat

Pono aide celui qui construit avec un agent à passer de projets éparpillés et fragiles à des
projets posés, suivis et durables, grâce à un atelier qui tient l'état réel de chaque projet et
refuse mécaniquement ce qui casse la production, **sans jamais retenir son code, ses données ni son
infrastructure**.

Le mandat complet : [docs/MANDAT.md](docs/MANDAT.md).

## Les quatre piliers

| Pilier | La phrase |
|---|---|
| **0 €** | Ton Claude, les paliers gratuits. Pas de crédits d'IA, pas de facture surprise. |
| **Ça tient** | Un agent ne peut pas casser ta prod, et tu es prévenu avant que tes quotas lâchent. |
| **Vite et juste** | Des canevas éprouvés : le code sort correct dès le départ. |
| **C'est à toi** | Ton GitHub, ta base, ton hébergement. Partir prend cinq minutes. |

## Carte du dépôt

| Chemin | Ce qu'il porte |
|---|---|
| `docs/` | Mandat, principes, positionnement, décisions, registre de vérité |
| `apps/web/` | La surface web : landing publique, puis la console |
| `.specify/` | Spec Kit : constitution, gabarits, workflow |
| `CLAUDE.md` | Le contexte du projet — lu par tous les agents |
| `AGENTS.md` | Le point d'entrée des agents non-Claude, renvoie vers `CLAUDE.md` |

## Les branches

```
main       le geste humain seul. Rien n'y entre sans validation.
dev        le terrain de l'agent.
NNN-slug   une branche par phase, nommée par Spec Kit.
```

## Développer

```bash
pnpm install
pnpm --filter @pono/web dev
```

## Outillage

- Node 22 · pnpm 11
- TanStack Start · Vite · Tailwind 4 · TypeScript
- Spec Kit : `v0.16.0` (`5dce710ce099067c7d3f2ef47a37b9a1c300b327`), exécuté par `uvx`.

## État

Base posée. Première tranche à venir : l'atelier qui tient les projets existants.
