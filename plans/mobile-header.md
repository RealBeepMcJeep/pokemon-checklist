# Compact mobile header — C

## Settled scope

The owner selected C from five real browser-rendered prototypes and explicitly approved implementing/deploying it on mobile only. Preserve all useful original information and controls; app version/build-source hash moves to the Settings footer. Desktop retains its existing layout. Do not change save/schema/sync/capture math or QR artifacts.

## Behavior / preservation map

1. At the top, show app identity and full game name above commands and labeled totals. Scrolling past90px contracts to a fixed55px single-row game/count/Dex/Tools/Settings bar; returning to top expands. A stable112px base layout spacer plus the measured alert-region height prevents scroll/height oscillation without covering the first section. Existing≤999px drawer breakpoint applies; desktop≥1000px retains its original header and held-clears/progress/notice order. Respect reduced motion and44px targets.
2. Always show mutually exclusive global Not caught / Seen / Caught. The small three-color rail represents their composition, not caught-only completion. Original caught-only progress remains in Settings; form totals reflect the active mode.
3. Settings owns the one actual Game mode selector, Track forms toggle, Backup/Restore/Reset and file input, full account identity/sign-in/sign-out and full sync status. Existing guards and handlers remain intact. No duplicate action IDs or hidden extra copies to appease tests.
4. Footer retains app identity, full mode/story-order/National Dex001–807 context and runtime BUILD_LABEL. Generated artifacts normally name their preceding build-source commit (N-1), not the enclosing release commit; this is the existing stamp contract, not drift.
5. Keep offline/pending/error/connecting/elsewhere/outdated warnings, HeldClears safeguards and Undo/view-only notices visibly actionable outside closed Settings. Compact only healthy sync prose. Opening Settings while signed out must remain network-silent on mobile user agents.
6. Native dialog handles focus trapping/Escape; return focus and body overflow are restored on close and crossing desktop breakpoint. New actionable/error notices close Settings so the existing eight-second Undo/recovery controls are immediately reachable. Drawer/Tools transitions must not leave Settings active or lock the page behind a removed dialog.

## Verification / limitations

Frozen parent contract: tests/header-c-contract.spec.ts, blob4e0074f43097e974aac6db40323c118448b0cd7b; observed both-project missing-trigger RED, then GREEN. Additional tests cover top/scrolled geometry, compact labels, modal/resize cleanup and mobile-UA network silence. Authenticated warning presentation uses simulated signals/unit tests, not real-account mutations. Hardware/Safari behavior is not proven by Chromium emulation.

Parent requires complete full gates, independent design/preservation review, commit/mirror/CI/Pages/live-byte verification and real live browser screenshots before announcing deployment. Temporary evidence stays outside this public repository. The owner authorized direct integration after review, no PR.
