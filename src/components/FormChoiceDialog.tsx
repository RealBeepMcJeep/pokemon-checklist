import { useEffect, useRef } from "preact/hooks";
import { pendingFormEdit, formEditContext, cancelFormEdit, applyFormEdit } from "../ui";
import { isCurrentFormEdit, resolveFormEdit } from "../form-edit";
import { regionalDetails } from "../regional";
import { showNotice, activeSaveKey } from "../state";
import { STATUS_LABEL } from "../domain";
import { stillEditingAfterDialog } from "../editing";

export function FormChoiceDialog() {
  const request = pendingFormEdit.value;
  const ref = useRef<HTMLDialogElement>(null);
  const current = request ? formEditContext(request.before.id) : null;
  const fresh = !!request && !!current && isCurrentFormEdit(request, current);
  useEffect(() => {
    if (request && !fresh) {
      cancelFormEdit();
      showNotice("This checklist changed. Choose again; no changes were made.", "error");
    }
  }, [request, fresh]);
  useEffect(() => {
    const dialog = ref.current;
    if (!request || !dialog) return;
    const focus = document.activeElement as HTMLElement | null;
    dialog.showModal();
    return () => {
      dialog.close();
      if (focus?.isConnected && activeSaveKey() === request.before.namespace)
        focus.focus({ preventScroll: true });
    };
  }, [request]);
  if (!request) return null;
  const decision = resolveFormEdit(request);
  if (decision.kind !== "choose") return null;
  const action = request.action;
  const next = action.kind === "status" ? STATUS_LABEL[action.next] : action.next ? "Favorite" : "Remove favorite";
  return <dialog ref={ref} class="form-choice-dialog" aria-labelledby="form-choice-title" aria-describedby="form-choice-description"
    onCancel={event => { event.preventDefault(); cancelFormEdit(); }}
    onKeyDown={event => {
      if (event.key === "Escape") event.stopPropagation();
      if (event.key !== "Tab") return;
      const buttons = [...event.currentTarget.querySelectorAll<HTMLButtonElement>("button:not(:disabled)")];
      const first = buttons[0], last = buttons[buttons.length - 1];
      if (event.shiftKey && document.activeElement === first) { event.preventDefault(); last?.focus(); }
      else if (!event.shiftKey && document.activeElement === last) { event.preventDefault(); first?.focus(); }
    }}>
    <h2 id="form-choice-title">Choose regional form</h2>
    <p id="form-choice-description">Choose one form to {action.kind === "status" ? `mark ${next}` : action.next ? "star" : "unstar"}. The other form will not change.</p>
    {request.before.legacyFavorite && action.kind === "favorite" && <p class="form-ownership-warning">{action.next
      ? "Assign the existing favorite to one form. Ownership will not change."
      : "The existing favorite has no assigned form. Choose which form it referred to, then unstar that form."}</p>}
    <div class="form-choice-options">
      {decision.forms.map(form => {
        const facts = regionalDetails(request.before.id, form)!;
        const name = facts.name;
        return <button class="action-button form-choice-option" type="button" key={form} disabled={!fresh}
          aria-label={action.kind === "status" ? `Mark ${name} as ${next}` : `${action.next ? "Star" : "Unstar"} ${name}`}
          onClick={async () => {
            if (!(await stillEditingAfterDialog())) { cancelFormEdit(); return; }
            applyFormEdit(request, form);
          }}>
          <strong>{name}</strong>
          <span>{facts.types.join(" / ")} · Currently {STATUS_LABEL[request.before.statuses[form]]}</span>
          <span>{request.before.favorites[form] ? "Favorite recorded" : "No form-specific favorite"}</span>
          <span>{action.kind === "status" ? `Mark as ${next}` : action.next ? "Star this form" : "Unstar this form"}</span>
        </button>;
      })}
    </div>
    <button class="action-button form-choice-cancel" type="button" onClick={cancelFormEdit}>Cancel</button>
  </dialog>;
}
