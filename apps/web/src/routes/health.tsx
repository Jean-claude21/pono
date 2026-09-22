import { createFileRoute } from "@tanstack/react-router";

// Container health probe, polled by the Dockerfile HEALTHCHECK.
export const Route = createFileRoute("/health")({
  component: Health,
});

function Health() {
  return <span className="sr-only">ok</span>;
}
