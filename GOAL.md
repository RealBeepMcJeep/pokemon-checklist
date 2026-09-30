# Five objective-based story teams

Approved by the owner in chat: replace OG / no-OG / three diverse mixed options with these five independent objectives. Butterfree is fixed in slot 1 on every six-member card; five battlers follow. Read-only synced roster analysis; do not modify checklist, favorites, sync or UI. All old family bans are cleared by default; explicit CLI exclusions may remain optional. Shared members and identical parties are allowed, with an explanation rather than forced diversification.

## Rules
1. OG: owned stage and all proposed stages/endpoints are original 151, Kanto forms; hard eligibility, then type synergy > uncaught evolution opportunities > practical endgame viability.
2. Non-OG: owned stage and proposed stages/endpoints not original 151; Butterfree exempt. Same priority order.
3. Mixed: unrestricted Dex numbers; no mandatory mix of generations. Same priority order.
4. Pokédex: each battler has a remaining evolution path of ordinary level-up steps only and adds at least one not-yet-caught entry. Butterfree exempt. No friendship, stones, trades, held items, or unconfirmed sex/stat/form gates. Maximize new entries, then type synergy, then viability. Count unseen intermediate stages too, even if the final is already owned, when a caught lower stage can actually earn those entries.
5. Best: practical buildable endgame strength first, then team synergy; no evolution or favorite bonus that displaces a stronger selection. Obtainable Gen VII/Prismatic Standard moves and items only; never assume hidden abilities, breeding, sex or regional form. Label inability to prove individual abilities/held items. This is a deterministic tier/viability heuristic, not a battle simulator, Nash equilibrium or proven game-wide optimum.

Type synergy is a separately exposed quality-independent measure of offensive type potential, defensive switching, duplicated types/common weaknesses, including Butterfree; use transparent components and lexicographic priority, not the old blended tier/evolution score. Favorites only break exact objective ties. Normal-ability feasibility must account for all hidden-ability-dependent candidates, not only prior hardcoded exceptions. Verify local Standard overrides and commit-pinned Gen VII data. Do not claim actual coverage from a STAB proxy; four labeled editorial move targets on cards are independently acquisition-checked. Warn if a category has fewer than five independent eligible caught lineages; do not fill it illegally.

## Interfaces and boundaries
Preserve existing non-story team_synergy.py CLI behavior. Reuse roster loading, parsers, pinned cache and existing Pillow sprite-card renderer. Add source caught IDs and objective/search-scope metadata to private structured snapshots. Prefer full eligible-pool search for Best; if any bound is essential, expose the excluded count, never call it exact, and validate pruning against fuller search where feasible. No arbitrary NU quality floor before synergy-first selection. Distinguish owned -> planned endpoint, already-caught final, unseen intermediates and pure-level vs item/other gates. Cache-backed tests must be portable. Old snapshots should render sensibly offline where feasible.

## Milestones
- [ ] Baseline current upstream, archive superseded interrupted patch, commit this spec.
- [ ] RED tests, selector / CLI / card objective migration, focused + full Python gates; commit reviewed code.
- [ ] Fresh live roster run; exactly five cards; acquisition and objective checks; visually inspect all five.
- [ ] Re-read source caught set; equality or regenerate. Update docs/changelog, integrate to current main, push and read back exact hash; clean worktrees.

## Acceptance and definition of done
Run npm run check under Node 22 and declared Python dev venv, Python analysis suite with verified cache, CLI with --story-options --json --uid YcKNGfydqSWI2ezzIv5ScetCxKQ2 --cache /opt/data/cache/scratch/pokemon-showdown-gen7, and existing renderer. Test all category boundaries, no bans default, strict priority conflicts, unrestricted Mixed, permitted duplicate parties, pure-level multi-step evolution with unseen intermediate, owned final no false new-final bonus, infeasible categories, Butterfree ownership, ordinary ability caveats, and source caught IDs. Inspect all five PNGs and long move/evolution labels. Private JSON/images stay outside public git. CLI-only work does not rebuild or deploy website. Verify the tool on committed current main and push readback before claiming shipped. Parent owns docs/changelog/integration; child code only to assigned worktree. Remove GOAL.md as a separate final cleanup once finished, retaining durable spec in docs/story-team-options.md.

## Deliberately out of scope
No battle simulator, EV/IV optimizer, breeding/SOS farming, new sync schema, site controls, scheduled jobs or roster repair. No forced party diversity.
