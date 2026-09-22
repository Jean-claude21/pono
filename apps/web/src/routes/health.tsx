import { createFileRoute } from "@tanstack/react-router";

// Sonde de santé du conteneur, interrogée par Coolify et par le HEALTHCHECK du Dockerfile.
export const Route = createFileRoute("/health")({
  component: Sante,
});

function Sante() {
  return <span className="sr-only">ok</span>;
}
