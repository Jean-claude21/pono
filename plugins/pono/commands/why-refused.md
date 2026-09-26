---
description: Why was this release refused, and what would fix it?
argument-hint: "[project name]"
---

Use the Pono tools to explain why a release was refused: $ARGUMENTS

Find the project with `list_projects`, then read its releases with `list_releases`. For each
refused release, name the failing guard, the file and line of each finding, and what would let it
pass. Never show a secret's value. Once the change is fixed and pushed, `evaluate_release` asks
for a new evaluation; approving a release stays a gesture of the person, in the console.
