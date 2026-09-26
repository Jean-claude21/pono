import { createFileRoute } from "@tanstack/react-router";
import { relay } from "@/lib/relay";

export const Route = createFileRoute("/api/$")({
  server: {
    handlers: {
      ANY: ({ request }) => relay(request),
    },
  },
});
