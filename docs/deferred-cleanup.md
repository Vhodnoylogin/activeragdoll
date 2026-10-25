# Reset-only deferred collision cleanup fence

The private cleanup epoch prevents an old `RemoveNonRagdollRigidBodiesFromWorldTask`
from resolving an actor's replacement graph manager after `ResetObjects`. It adds
no public service or001 changes, and does not change constraint restoration,
ragdoll removal, ordinary furniture timing or inactive fallback calls.

All three cleanup enqueue hooks capture the current numeric ticket at hook entry,
before owner/active queries. Furniture entry retains that ticket through its delayed lambda;
it must not capture a replacement ticket when the delay finishes. The task checks
its saved ticket before handle lookup. Both old delayed jobs and tasks already
submitted to SKSE therefore remain harmless after reset; they are not drained or
removed from the task queues by this repair.

`ResetObjects` invalidates the epoch before clearing old tracking. The numeric owner
prepares a pure next state and publishes through one private commit under a mutex.
Its lock is released before engine lookup, graph access or cleanup. Generation
exhaustion retires the owner without wrapping, so old tickets never revive.

This is a reset-only admission fence. Same-epoch deactivation/reactivation and graph
replacement remain outside it. A task already admitted before a truly concurrent
reset is not made atomic with its engine call. No task-thread serialization,
complete physics lifetime, actor endpoint or world ownership guarantee is added.
There is no new PreLoad handling: only existing calls to `ResetObjects` invalidate
these tickets. Existing constraint-restoration call order remains unchanged.

Run `python tests/run_cleanup_epoch_tests.py --build-dir <new external directory>`.
It compiles the actual task, all three hooks, delayed queue and reset function
against explicit engine doubles. It checks current work, stale delayed/queued work,
replacement managers, invalid handles/actors/managers, repeated reset and terminal
counter exhaustion, including reset after an active-query result. Removing the Run
guard, capturing after the active query, or recapturing a new ticket in the delayed
lambda must fail separate negative controls. It also verifies that the constraint-
restoration/removal functions and official001 bytes remain unchanged. The default
constraint baseline is pinned to `986a3e7ca5cb42a01934ba0b957aec36fc0930c7`;
an explicit `--baseline` override is recorded in the evidence manifest.
The existing lifecycle suite remains applicable. These are source-level CPU tests;
native PLANCK remains unbuilt and unqualified in Skyrim.
