# Contract: task-2.apply-fixes.apply-all-fixes.apply-all-fixes.apply-atomic-edit

## Inputs
- scripts/kanban-viewer.html — the single self-contained HTML file to edit
- Current CSS: two .drop-zone rule blocks (lines 110-119 properties block, line 121 cursor:pointer standalone rule) that must be merged
- Current CSS: dark theme (:root/[data-theme='dark']) defines 16 custom properties (lines 8-26)
- Current CSS: light theme ([data-theme='light']) defines 16 custom properties (lines 28-45)
- Current JS: validateKanban function (lines 439-450) — read-only, must not be modified
- Current DOM: element ids (drop-zone, file-input, filter-input, tree-container, etc.) and class-driven filter/collapsed logic used by JS

## Outputs
- Modified scripts/kanban-viewer.html with exactly one .drop-zone CSS rule containing all original properties (margin, padding, border, border-radius, text-align, color, font-size, transition, cursor:pointer)
- Dark and light theme blocks each define an identical set of custom property names (current state: both already define 16 — acceptance criteria says 14; verify and reconcile)
- File remains valid, parseable HTML with no JS behavioral changes

## Constraints
- Atomic edit: single commit, single file change
- Exactly one .drop-zone CSS rule must exist after edit (merge lines 110-121 into one block)
- cursor:pointer must be present in the merged .drop-zone rule
- validateKanban function (lines 439-450) must be byte-identical before and after edit
- All DOM element ids must remain unchanged (drop-zone, file-input, filter-input, tree-controls, tree-container, etc.)
- Filter logic (.filter-hidden, .filter-match classes) and collapsed logic (.collapsed class) must remain untouched
- Dark and light theme blocks must define identical sets of custom property names
- .drop-zone.dragover rule (lines 123-126) is a separate selector and must be preserved as-is
- No external dependencies may be introduced (Constitution §3)
- Post-edit file must parse as valid HTML
