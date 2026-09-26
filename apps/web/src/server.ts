import { paraglideMiddleware } from "./paraglide/server.js";
import handler from "@tanstack/react-start/server-entry";
import { isAgentPath, relay } from "./lib/relay";

export default {
  fetch(request: Request): Promise<Response> {
    // Agents' protocol paths carry no page and no language: straight to the service.
    if (isAgentPath(new URL(request.url).pathname)) return relay(request);
    // Every other request resolves its language before rendering, so server-rendered text
    // matches it.
    return paraglideMiddleware(request, () => handler.fetch(request));
  },
};
