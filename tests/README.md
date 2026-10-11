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
guarantee. No endpoint ABI is added.

Windows checks use MSVC C++20 `/EHsc /W4 /WX`. Exception restoration is qualified
under those fixture flags; the native Release project does not explicitly enable
the same exception model. This is not a whole-plugin exception guarantee.

The native plugin still needs its external SKSE and Havok dependencies and separate
game qualification. The fixture does not check native layouts, hook addresses,
event scheduling or Havok cleanup and does not install or launch the game.
