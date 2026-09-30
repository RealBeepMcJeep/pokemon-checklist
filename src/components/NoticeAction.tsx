import { useEffect, useState } from "preact/hooks";
import { notice, readOnly, type Notice } from "../state";

/**
 * The notice's one-tap action (Undo, or a recovery download), floating at the bottom
 * of the screen. The header's own notice line scrolls away on a phone and sits
 * behind the Pokédex drawer, which is exactly where most taps happen. The message
 * itself is still announced by the header's live region, so this bar is not one.
 * An Undo hides after a few seconds; an error's recovery action stays until the
 * next notice replaces it.
 */
export function NoticeAction() {
  const current = notice.value;
  const [hidden, setHidden] = useState<Notice | null>(null);
  useEffect(() => {
    if (!current.action || current.kind === "error") return;
    const timer = setTimeout(() => setHidden(current), 8000);
    return () => clearTimeout(timer);
  }, [current]);
  if (!current.action || hidden === current) return null;
  return (
    <div class={`notice-action ${current.kind}`}>
      <span>{current.message}</span>
      <button
        class="action-button"
        id="notice-action"
        type="button"
        // An Undo in a view-only tab would change nothing; Reload still works.
        disabled={current.action.label === "Undo" && readOnly.value !== null}
        onClick={current.action.run}
      >
        {current.action.label}
      </button>
    </div>
  );
}
