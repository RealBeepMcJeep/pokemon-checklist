import { CatchCalculator } from "./CatchCalculator";
import { signal } from "@preact/signals";
import { useEffect, useRef } from "preact/hooks";
export const toolsOpen = signal(false);
export function Tools() {
  const ref = useRef<HTMLDialogElement>(null);
  const open = toolsOpen.value;
  useEffect(() => {
    if (open) ref.current?.showModal();
    else if (ref.current?.open) {
      ref.current.close();
      document.getElementById("tools-toggle")?.focus();
    }
  }, [open]);
  return (
    <dialog
      ref={ref}
      id="tools-panel"
      aria-labelledby="tools-title"
      onCancel={() => {
        toolsOpen.value = false;
      }}
    >
      <div class="tools-heading">
        <h2 id="tools-title">Catch calculator</h2>
        <button
          type="button"
          class="action-button"
          onClick={() => {
            toolsOpen.value = false;
          }}
        >
          Close tools
        </button>
      </div>
      <CatchCalculator />
      <nav aria-label="QR tools">
        <a href="qr.html">QR archive</a>
        <a href="qr-experimental.html">Experimental QR</a>
      </nav>
    </dialog>
  );
}
