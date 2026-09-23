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
| `apps/web/` | La surface web : landing publique et console (TanStack Start) |
| `apps/api/` | Le service FastAPI et le worker : domaine, adaptateurs, relevés |
| `packages/design/` | Le système visuel, source unique |
| `packages/sdk/` | Le client TypeScript, généré depuis l'OpenAPI du service |
| `specs/` | Les phases conduites par Spec Kit |
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
uv sync
pnpm api:dev                 # service sur :8000 (variables : apps/api/.env.example)
pnpm --filter @pono/web dev  # console sur :3000
pnpm check:all               # contrôles du service et de la console
```

## Outillage

- Node 22 · pnpm 11 · Python 3.14 · uv
- TanStack Start · Vite · Tailwind 4 · TypeScript · Paraglide JS
- FastAPI · SQLAlchemy async · Alembic · Postgres (Neon) avec RLS forcée
- Spec Kit : `v0.16.0` (`5dce710ce099067c7d3f2ef47a37b9a1c300b327`), exécuté par `uvx`.

## État

Phase 1 livrée sur `dev` : l'atelier tient l'état réel des projets importés — environnements,
liens vérifiés, derniers déploiements, quotas et alertes — en français et en anglais.
