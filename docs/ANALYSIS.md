# Analysis contract and limits

The application is a bounded source model. It never executes a game's Python
functions to analyze them. Native validation is a separate, explicitly invoked
test harness using private game/engine copies.

## Relevant state

Intermediate assignment dependencies are tracked, not just names directly used
in a condition. Memoization includes future-relevant scalar values, their types,
and the actual caller continuation. Irrelevant earlier choices do not create
distinct future states. `True` is not conflated with `1`; unknown is not a string
sentinel or a default zero.

## Incoming contexts

A forward worklist joins every modeled earlier choice at the same program point
and call context. Equal scalar values/types remain known; differences become
unknown. It does not sample paths. Joins can lose correlations, causing additional
neutral results, not permission to invent stronger proof.

Coverage completion and outcome certainty are separate. The JSON report includes
`simulation`, per-menu `context_coverage`, `analysis_policy`, and `decision_verified`.
A completed global solver can still have incomplete entry coverage if opaque
Python might jump or re-enter another menu.

Static calls preserve caller return points. Empty conditional menus fall through;
unknown visibility also includes the all-hidden possibility. Default-store runtime
aliases are normalized. Persistent defaults are not assumed to reset on new game.

## Fail-closed cases

Unmodeled initialization, arbitrary calls/control, callbacks, API rebinding,
unsupported label/call parameters, return expressions, named Python stores,
local-label syntax, and menu set/argument constructs can prevent certification.
Literal defaults and a narrow native Character name/color declaration are not a
general initialization interpreter. Special objects, exceptions, callbacks,
missing sources, and runtime state are not fully modeled.

Cycles are not assumed to terminate safely. Budget, depth, context, or observation
limits do not turn partial results into proof. Defaults are 300,000 global steps
and depth 2,500; local fallback uses 3,000/200. Context analysis uses its own bounded
worklist and shared continuation budget. More preparation work can increase total
scan time even if memoization reduces the number of simulated steps.

## Meaning of decisions

Narrative wording, label spelling, and an opened condition do not establish death,
survival, or benefit. A heuristic is not retained as a definitive color merely
because some solver output exists. A safety result concerns supported source
control and a safe future choice strategy, not every possible later player action
or all endings of a commercial game.

Do not disable `contract_enforcement` for ordinary use. That bypasses the
conservative color contract. The optional legacy bridge profiles are not evidence
that the automatic planner can prove every game-specific route.
