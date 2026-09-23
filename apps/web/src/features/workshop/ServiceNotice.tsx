import { errorMessage } from "@/lib/i18n";

/** A service error, in the person's language, from its stable code (FR-005). */
export function ServiceNotice({ code }: { code: string }) {
  return (
    <div className="verdict" role="alert" style={{ marginTop: 28 }}>
      <p>{errorMessage(code)}</p>
    </div>
  );
}
