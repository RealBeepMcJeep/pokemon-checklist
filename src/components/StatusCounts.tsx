export interface CollectionCounts {
  none: number;
  seen: number;
  caught: number;
}

/** Visible labels carry the order; color is supplemental, never the only key. */
export function StatusCounts({ counts, label }: { counts: CollectionCounts; label: string }) {
  return (
    <span class="status-counts" role="group" aria-label={`${label}: Not caught ${counts.none}, Seen ${counts.seen}, Caught ${counts.caught}`}>
      <span data-status="none">Not caught {counts.none}</span>
      <span class="status-count-separator" aria-hidden="true"> / </span>
      <span data-status="seen">Seen {counts.seen}</span>
      <span class="status-count-separator" aria-hidden="true"> / </span>
      <span data-status="caught">Caught {counts.caught}</span>
    </span>
  );
}
