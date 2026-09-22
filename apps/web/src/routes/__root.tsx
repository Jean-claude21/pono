import type { ReactNode } from "react";
import { createRootRoute, HeadContent, Outlet, Scripts } from "@tanstack/react-router";
import appCss from "@/styles/app.css?url";

export const Route = createRootRoute({
  head: () => ({
    meta: [
      { charSet: "utf-8" },
      { name: "viewport", content: "width=device-width, initial-scale=1" },
      { title: "Pono — pose, ça tient" },
      {
        name: "description",
        content:
          "Le poste de contrôle des projets construits par agent. Ton GitHub, ta base, ton hébergement.",
      },
    ],
    links: [{ rel: "stylesheet", href: appCss }],
  }),
  component: Root,
});

function Root() {
  return (
    <Document>
      <Outlet />
    </Document>
  );
}

function Document({ children }: Readonly<{ children: ReactNode }>) {
  return (
    <html lang="fr">
      <head>
        <HeadContent />
      </head>
      <body className="bg-stone-50 text-stone-900 antialiased">
        {children}
        <Scripts />
      </body>
    </html>
  );
}
