import { createFileRoute } from "@tanstack/react-router";
import * as m from "@/paraglide/messages.js";
import { calendarDay } from "@/lib/format";
import { LocaleSwitcher } from "@/features/i18n/LocaleSwitcher";

// Every statement below ties to a line of docs/VERITE_ET_PREUVES.md (003 FR-016, SC-006).
// Change one without the other and the page says more than the register: refused.
const UPDATED = "2026-09-26";
const CONTACT = "messanjeanclaude@gmail.com";

export const Route = createFileRoute("/privacy")({
  head: () => ({ meta: [{ title: m.privacy_meta_title() }] }),
  component: Privacy,
});

function Section({ title, items }: Readonly<{ title: string; items: string[] }>) {
  return (
    <section>
      <h2>{title}</h2>
      <ul>
        {items.map((item) => (
          <li key={item}>{item}</li>
        ))}
      </ul>
    </section>
  );
}

function Privacy() {
  return (
    <>
      <header className="site-header">
        <a className="monogram" href="/">
          <b>P</b>Pono
        </a>
        <LocaleSwitcher />
      </header>
      <main className="page doc">
        <p className="mono-label">{m.privacy_label()}</p>
        <h1>{m.privacy_title()}</h1>
        <p className="lede">{m.privacy_intro()}</p>
        <p className="mute" style={{ fontSize: 13 }}>
          {m.privacy_updated({ date: calendarDay(UPDATED) })}
        </p>

        <Section
          title={m.privacy_reads_title()}
          items={[m.privacy_reads_identity(), m.privacy_reads_code(), m.privacy_reads_hosting()]}
        />
        <Section
          title={m.privacy_keeps_title()}
          items={[
            m.privacy_keeps_facts(),
            m.privacy_keeps_keys(),
            m.privacy_keeps_tokens(),
            m.privacy_keeps_place(),
          ]}
        />
        <Section
          title={m.privacy_never_title()}
          items={[
            m.privacy_never_secrets(),
            m.privacy_never_code(),
            m.privacy_never_other(),
            m.privacy_never_sell(),
          ]}
        />
        <section>
          <h2>{m.privacy_agents_title()}</h2>
          <p>{m.privacy_agents_body()}</p>
        </section>
        <section>
          <h2>{m.privacy_remove_title()}</h2>
          <p>{m.privacy_remove_body()}</p>
        </section>
        <section>
          <h2>{m.privacy_contact_title()}</h2>
          <p>
            <a href={`mailto:${CONTACT}`}>{CONTACT}</a>
          </p>
        </section>
      </main>
    </>
  );
}
