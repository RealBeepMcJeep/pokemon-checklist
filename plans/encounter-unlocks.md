# Encounter unlocks — owner-approved contract

## Scope
Prismatic Moon first. Vanilla datasets list SOS target species without caller IDs;
controls are hidden/ignored there until caller-access mapping is verified. Five flags:
Tauros Charge, Surfing, Fishing, SOS Calls, and Weather SOS (one flag). Route-8-only
and other unrequested restrictions remain return-later; weather/time notes remain visible.

## Domain
Unique reachable species drive location counters, completion, Catch next and occurrence
labels. Start from regular wild rows plus enabled travel methods; close SOS reachability
through accessible callers and weather targets until stable. Weather needs both SOS and
Weather SOS plus a reachable encounter. Caught ownership does not unlock an inaccessible
caller. No species/form/favorite status changes when flags change. Empty locations stay
explicit. Backtrack means the regular baseline is nonempty/all caught and the expanded
eligible set has uncaught species; it disappears once caught or the flag is disabled.
Do not auto-jump the reader when a checkbox changes.

## Persistence and safety
Save v4 stores exact, unique unlock IDs in settings; defaults off on v1–v3 migration.
Both offline and UID-namespaced old keys and their last-good copies remain untouched.
Backup/Restore/Reset, cross-tab and per-record account sync carry flags. Migration must
not invent clears for fields missing in an old save. New flags use on/off; the deployed
rules reject older clients' unknown-key none clears. Old clients may need reloading to
continue publishing after flags are present. Existing authentication/allowlist rules are
unchanged. Do not seed abilities from a roster or automatically alter account flags.

## UI and acceptance
Mobile Settings preserves all existing controls/footer; desktop adds a Settings dialog
for unlocks. Close the modal and release body scroll on breakpoint transitions. Five
44px checkbox rows, read-only guards, signed-out network silence, locked counts and
backtrack markers. Preserve global 807-species/form semantics. Verify migration, exact
save validation, caller/water/weather dependencies, graph closure, unique totals, disabled
flags without deleting catches, reload, desktop/mobile/file/HTTP and backup/restore.

## Runtime rule-layout drift
The existing live rules grant the owner write access at the UID parent, while the
repository's pre-release copy grants it at state/log children. The release deploys only
the new records-validation guard as an overlay onto the freshly read live tree, preserving
all unrelated live permissions. Exact guard/full-overlay readback and unauthenticated
401 read/write checks were verified. Reconciling the older rule layout is separate work;
do not replace it blindly with the repository file during this release.

## Publication
Run the full Node-22/Python/browser gates; disclose failed/retried runs. Deploy/read back
the narrow security-rule guard before the app; push primary Gitea only, verify exact
source and GitHub mirror, CI/Pages commit and live bytes/controls. Keep personal snapshots
outside git. Close issue #3 only after real live verification.
