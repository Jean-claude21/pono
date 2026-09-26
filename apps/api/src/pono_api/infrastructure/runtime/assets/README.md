# Pono development runtime

These files let Pono run this project's development server on your own server, and show each
change in a few seconds.

- `Dockerfile` builds the runtime from the development branch.
- `gate.mjs` stands in front of the dev server: only members signed in to Pono reach it; files
  written by Pono apply at once and are saved to the development branch; the branch is followed
  without overwriting unsaved writes; errors are kept for Pono to read; the dev server sleeps after
  a quiet while.
- `dev.mjs` starts Vite with this project's own configuration.

The runtime never connects to the production database. Remove this folder to stop using it: the
project keeps running without Pono.
