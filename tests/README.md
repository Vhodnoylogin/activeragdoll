# Lifecycle regression checks

Run from the checkout with an output directory outside Git:

```text
python tests/run_lifecycle_regressions.py --build-dir <external-directory>
```

The runner extracts and compiles the actual `ResetObjects`, locked movement and
look-at membership helpers, and hit-dispatch hook from `src/main.cpp`, inserting
them unchanged into `lifecycle_fixture.cpp.in`. The fixture supplies a fake engine
and lock-checking maps. It exercises prior-state revocation, new state after reset,
concurrent reset/lookup, every nested extended/ordinary dispatch combination,
exception restoration and the original extended/physics event payloads. Generated
source, binaries and a source-hash manifest stay in the external directory.

Official001 header/getter hashes and consumer helper use are supplemental
structural guards. The movement/look-at engine consumers themselves are not built
by this fixture. Current-event behavior covers synchronous calls routed through
the repaired dispatch hook; direct event sends elsewhere bypass it. The pointer
remains legacy process-global state, with no concurrent-dispatch or retained-pointer
guarantee. These earlier lifecycle repairs alone add no endpoint ABI; the separate
cooperation API suite below covers revision 2.

Windows checks use MSVC C++20 `/EHsc /W4 /WX`. Exception restoration is qualified
under those fixture flags; the native Release project does not explicitly enable
the same exception model. This is not a whole-plugin exception guarantee.

The native plugin still needs its external SKSE and Havok dependencies and separate
game qualification. The fixture does not check native layouts, hook addresses,
event scheduling or Havok cleanup and does not install or launch the game.

The separate reset-only deferred cleanup fixture runs with
`python tests/run_cleanup_epoch_tests.py --build-dir <new external directory>`.
It executes all three production enqueue hooks, the delayed queue, cleanup task
and reset, including already-queued work and separate stale-run/recaptured-ticket
negative controls. See [its bounded contract](../docs/deferred-cleanup.md).
# Additive cooperation API checks

`python tests/run_synergy_tests.py --build-dir <external-directory>` compiles the
actual production `src/synergy_runtime.cpp`, a C11 consumer and C++ checks with
warnings treated as errors. It covers owner isolation, generations/reset/loading,
concurrent coherent snapshots, endpoint leases, callback self-removal/client close
and concurrent drainage, scoped hit veto/scale decisions, immutable results and
terminal cancellation during 300 target-invalidation cycles, capsule geometry request commitments and a separate native-provider endpoint bridge.
An additional actual-source fixture extracts the native clutter hit method and
actor publisher, live endpoint resolver and native geometry adapter, checking veto/scale before engine commitment and publication
under graph/world ownership, physical destruction at world unlock without stale
republication, publication callbacks after lock release, independent cloned capsules, actual deferred adoption, and callback-scoped endpoint resolution. These use explicit fake engine objects; they do
not qualify native Havok layouts, hook installation or game behavior. Read the
[ABI/phase contract](../docs/synergy-api.md) for the exact delivered boundary.
