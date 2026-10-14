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

## Standalone persistence test initialization
The first release's CI retried one standalone reload case. Early instrumentation
found file-origin storage missing before app initialization, including an unrelated
sentinel. With early init-script access, a large blank HTML control reproduced
(5/100 reloads), as did the pre-unlock release (2/70) and current release (1/70).
Merely changing to a normal profile did not eliminate failures in repeated UI tests.

Removing early file-storage access isolated the trigger: private-context large blank
HTML and current app controls each retained their saves for 100 reloads. Normal-profile
controls also passed 100 reloads each plus browser/profile restart. Live HTTPS with
the original early hook passed 40 reloads. The observed failure is browser/test
initialization interaction, not evidence of a new unlock-code regression.

The test now seeds legacy v3 once after initial page/origin load, then reloads to
exercise migration. No init hook accesses or re-seeds storage on later reloads. Both
projects retain their original browser contexts and all original progress/eligibility
assertions; three consecutive reloads check saved flags, species and the real checkbox.
No production-code workaround or app-artifact rebuild is needed.

## Publication
Run the full Node-22/Python/browser gates; disclose failed/retried runs. Deploy/read back
the narrow security-rule guard before the app; push primary Gitea only, verify exact
source and GitHub mirror, CI/Pages commit and live bytes/controls. Keep personal snapshots
outside git. Close issue #3 only after real live verification.
