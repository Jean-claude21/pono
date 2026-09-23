import { createPonoClient } from "@pono/sdk";
import * as m from "@/paraglide/messages.js";
import { getLocale, locales, setLocale } from "@/paraglide/runtime.js";

type Locale = (typeof locales)[number];

const NAMES: Record<Locale, () => string> = { fr: m.locale_name_fr, en: m.locale_name_en };

/**
 * The explicit language choice (FR-003). It lands in the `pono_locale` cookie, which wins over the
 * browser language; for a signed-in person it is also saved on their profile, so it follows them.
 */
export function LocaleSwitcher({ signedIn = false }: { signedIn?: boolean }) {
  const current = getLocale();

  async function choose(locale: Locale) {
    if (locale === current) return;
    if (signedIn) {
      await createPonoClient().PUT("/api/v1/me/locale", { body: { locale } });
    }
    void setLocale(locale);
  }

  return (
    <div className="locale-switch" role="group" aria-label={m.locale_switch_label()}>
      {locales.map((locale) => (
        <button
          key={locale}
          type="button"
          lang={locale}
          aria-pressed={locale === current}
          title={NAMES[locale]()}
          onClick={() => choose(locale)}
        >
          {locale.toUpperCase()}
        </button>
      ))}
    </div>
  );
}
