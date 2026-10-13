export interface CollectionCounts {
  none: number;
  seen: number;
  caught: number;
}

/** Visible labels carry the order; color is supplemental, never the only key. */
export function StatusCounts({ counts, label, compact = false }: { counts: CollectionCounts; label: string; compact?: boolean }) {
  const value = (name: string, count: number) => compact ? <><span class="status-count-label">{name}</span>{" "}<strong class="status-count-number">{count}</strong></> : `${name} ${count}`;
  return (
    <span class="status-counts" role="group" aria-label={`${label}: Not caught ${counts.none}, Seen ${counts.seen}, Caught ${counts.caught}`}>
      <span data-status="none">{value("Not caught", counts.none)}</span>
      <span class="status-count-separator" aria-hidden="true"> / </span>
      <span data-status="seen">{value("Seen", counts.seen)}</span>
      <span class="status-count-separator" aria-hidden="true"> / </span>
      <span data-status="caught">{value("Caught", counts.caught)}</span>
    </span>
  );
}
