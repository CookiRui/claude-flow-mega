# Contract: task-2.apply-fixes.apply-all-fixes

## Inputs
- CSS audit: list of duplicate selectors to remove (e.g. `.drop-zone` defined twice at lines 110-119 and 121)
- CSS audit: complete set of theme tokens needed for both [data-theme='dark'] and [data-theme='light'] (currently both have matching tokens)
- CSS audit: confirmation that `.tree-node.filter-hidden` (display:none) and `.node-children.collapsed` (display:none) do not conflict when both applied to nested elements
- JS audit: DOM id inventory confirming all getElementById calls match actual HTML id attributes (total, done, running, pending, failed, cost, progress-bar, progress-bar-container, goal-bar, goal-text, error-banner, drop-zone, file-input, tree-container, tree-controls, filter-input, expand-all, collapse-all, auto-refresh, refresh-dot, theme-toggle, shortcuts-help)
- JS audit: confirmation no duplicate event listeners exist (each addEventListener call targets a unique element/event pair)
- JS audit: confirmation that render() already re-applies filter after renderTree() (lines 648-649)
- JS audit: confirmation that validateKanban() logic is correct and must remain unchanged

## Outputs
- Single self-contained kanban-viewer.html with all CSS and JS fixes applied atomically
- No behavioral regressions: theme toggle, auto-refresh, drag-drop, file browse, filter, expand/collapse, keyboard shortcuts all functional
- Clean CSS: no duplicate selectors, both themes define identical token sets, filter-hidden and collapsed classes coexist without conflicts
- Clean JS: DOM ids match HTML, no duplicate listeners, filter persists across re-renders, validateKanban unchanged

## Constraints
- All fixes must be applied in a single edit pass — no intermediate commits or partial states where the viewer is broken
- validateKanban() function signature and logic must not be modified
- File must remain a single self-contained HTML file (inline CSS + JS, no external dependencies)
- Both dark and light themes must have complete and matching token variable sets
- The duplicate `.drop-zone { cursor: pointer; }` at line 121 must be merged into the original `.drop-zone` block (lines 110-119), not left as a separate rule
- Filter state (filter-hidden/filter-match classes) operates on .tree-node elements; collapsed state operates on .node-children elements — these target different DOM levels and must remain non-conflicting
- Constitution §4 requires commit + push after the edit is verified
