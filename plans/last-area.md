# Last-opened area restoration

## Boundary

Persist a UI preference, not player progress. A dedicated `pokemon-checklist-last-area-v1:<save-namespace>:<mode>` local-storage key contains one validated location ID. Existing player schema, backup bytes, replica records and Firebase rules remain unchanged. Offline and signed-in namespaces do not share this preference.

## Transitions

- Initialization chooses an explicit known location/encounter hash, otherwise the remembered valid area, otherwise the existing first-incomplete fallback.
- Only game-mode or settled account-namespace changes rerun restoration. Species updates and visibility/pageshow events do not subscribe to it.
- Account switching batches the existing state transition and publishes the UI namespace after it settles. Location DOM is keyed by namespace/mode so lazy content, native details state and stale toggle closures do not leak across contexts.
- A manual summary opening supersedes an old in-app URL jump. Existing row jumps continue mounting and focusing their specific encounter rather than losing focus to a summary.
- Open toggles remember programmatic navigation too; closing a section retains the last-opened preference. A delayed toggle with an obsolete mode/namespace cannot write into the current context.
- Invalid/removed IDs and unreadable preference storage use the ordinary fallback. A failed preference write gives a once-per-page notice without marking player progress unsaved or breaking browsing.

## Acceptance

Browser regressions exercise manual open/reload and new-page reopening, phone/desktop scroll and focus, mode isolation, real local account transitions, explicit links, manual navigation after a link, corrupt preferences, storage failure and unchanged collection persistence. The source-import account fixture runs over Vite; the standalone file runs all offline scenarios. Existing full app gates remain required.
