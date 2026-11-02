# PLANCK additive cooperation API revision 2

The source implements the plain-C table in [planck_synergy.h](../include/planck_synergy.h). Request revision `2` through the existing SKSE PLANCK message's `GetApiFunction`, at PostPostLoad or later. Check the returned table's `version`, `size` and `capabilities` before using it. Revision 001, its vtable and its extended hit event are unchanged. This extension is development source, not a qualified native release.

## Ownership and callback lifetime

Register a unique UTF-8 client ID. Every endpoint, actor-policy lease, callback registration belongs to that client. Another client cannot release or query its resources. Tokens are process-local, monotonic and never serialized. RegisterClient zeroes its output on failure. Resource limits return `LIMIT`: 64 clients, 512 resources, 512 published actors, 256 bodies per actor, 16 hit policy callbacks and 256 retained hit snapshots.

`Unsubscribe` removes both event subscriptions and hit policy registrations. `ReleaseClient` closes the client and stops new callbacks before testing drainage. Both are nonblocking: `BUSY` means a callback is in flight; retry after it returns. Only `OK` confirms it is safe to free callback code/context. A callback can remove itself, but gets `BUSY` until it has returned. A closing client cannot acquire new resources. There is no background waiter, blocking unload or implicit DLL pin. `ReleaseLease` releases endpoints and actor policies. Geometry table entries are reserved and return `UNSUPPORTED`; there are no geometry request resources.

All public entry points contain C++ implementation exceptions. Callbacks must not throw or block. A throwing observer is retired; a throwing, malformed or slow hit policy is retired and vetoes that hit. Copy operations and nonblocking resource removal are allowed from callbacks. Registration, endpoint acquisition and new actor-policy requests return `REENTRANT` there. No callback may change live engine objects, inventory, damage or ragdolls. The copied decision is the only writable hit-policy output. Consumer teardown must drain every provider that still calls its code.

## Samples, generations and phases

Set every input/output record's `size` to `sizeof(record)` and zero reserved fields. The ABI fixes packing to 8 and uses fixed-width integer fields, POD records and caller buffers; it transfers no STL values or allocated memory. Vector units are meters, axes are the game's Havok axes. Capsule endpoints and endpoint attachment points are body-local; position/xyzw rotation map body-local to Havok world space. There is no player hand remapping: hit hand is right=0, left=1, unavailable=2.

`CopyActorPhysics` atomically copies actor metadata and its complete body array. On `BUFFER`, only required capacity is returned; retry to obtain one coherent sample. All copied bodies share the returned sample ID. Samples are observations from the main actor maintenance pass, not a promise that a cached pose stays live. Native publication acquires graph then world ownership and commits the registry copy before releasing either lock; publication observers dispatch afterward. The stored numerical native identities are comparison keys, never dereferenced by an executor. Samples include main-frame count, the separate prephysics-tick count, and PLANCK's frame time in seconds. Active ragdolls only are published; absence is `NOT_FOUND`, not an assertion that an arbitrary NPC has no collision or no body.

An endpoint contains an owned lease, actor handle, epoch, actor generation, body generation/index and copied local point. Acquire validates the exact publication; Validate checks ownership and current generations. Actor/model/ragdoll/body-list replacement, deactivation/unload, physical entity removal/deletion and world/load reset invalidate dependent endpoints and actor-policy leases. Invalidation callbacks name the old actor reference. Actor and body generation tokens never recycle within the process. A geometry revision is separate from body generation.

SKSE PreLoadGame suspends API publication, advances its epoch and cancels queued hit work; PostLoadGame (including failure) resumes publication. A successful load, NewGame or world replacement also resets physical tracking. Client identities and subscriptions survive reset. Global hit registrations survive; actor-scoped hit registrations retain their exact old reference and cannot attach to a replacement. Release retired resources explicitly. Geometry requests are unavailable.

| Operation/callback | Thread and phase contract |
|---|---|
| Public table calls | Any thread; copied registry access is mutex protected |
| Actor publication/events | Main actor maintenance, after releasing graph/world locks |
| Candidate/policy/terminal-hit callbacks | Synchronous committing thread; melee task thread or clutter/contact thread; may already hold world ownership |
| Entity invalidation/events | Synchronous physics removal/deletion thread; may hold world lock |
| Load/reset events | The engine's lifecycle thread |

Event and hit records include a provider-local process thread ID and phase. These IDs are descriptive, not OS handles or permission to mutate the engine. Callbacks run outside the API registry mutex, with no guarantee that an engine lock is absent. Events pass a callback-lifetime copied record. Hit event `subject` is its snapshot ID; query `CopyHitSnapshot` before retention eviction/reset. Actor events require a fresh actor copy. Endpoints provide validated descriptors, not a borrowed engine pointer or a physical constraint. HIGGS constraint submission/lifetime coupling is still a separate required integration; no native pointer resolver is advertised.

## Hit interpretation and commitment

`RequestActorPolicy` returns an immediate owned restriction lease for the exact actor generation. Suppress-hits is an OR across matching leases. Clutter damage scales use the smallest requested scale in [0,1]. Releasing one lease never restores or edits global PLANCK settings. These are commutative restrictions; registrations do not compete for an exclusive user action and do not use registration-time priority.

The native melee task calls BeginHit before swing/hit side effects. It refuses stale queued work and replacement hit nodes, and checks the node/reset fence again immediately before `HitActor`. Clutter calls BeginHit after populating HitData and before `Actor_GetHit`, cooldown and hitting-object damage. A veto skips those commitment side effects. The existing collision-detection/cooldown admission path before the melee task is unchanged; policy does not undo already observed contact.

Candidate observers cannot change the decision. Matching policies receive copied pending data, with veto-wins and minimum clutter scale. Callbacks must return within 1 ms; a measured overrun disables that policy and vetoes the current hit. The whole policy dispatch budget is 2 ms and at most 16 callbacks. These are cooperative deadlines: native C code cannot safely preempt a callback that never returns. Melee supports veto only (`proposedDamage=-1`); its engine damage is not yet known. Clutter supplies proposed engine damage, and its effective damage fields are scaled before commitment. No claim is made that the post-mitigation health loss equals this proposal. Numeric melee damage rewriting is not advertised.

BeginHit snapshots remain pending until the actual native commitment or early-return cancellation calls FinishHit. A denied hit is already terminal. FinishHit publishes exactly one immutable allowed/cancelled result and cannot turn a denial into an allowed result. Target invalidation during policy processing stores a terminal cancelled snapshot and emits one terminal event; FinishHit cannot recommit it. A reset that already evicted the snapshot does not recreate an old-epoch record or emit a hit event referring to that evicted snapshot. `HIT_COMMITTED` means a final PLANCK processing outcome, including denied/cancelled, not proof of health loss. This API covers PLANCK player melee and PLANCK clutter physics damage, not every ordinary engine/spell/projectile hit.

## PPB geometry proposals remain unavailable

The table reserves geometry proposal/result/cancellation entries, but the capability `PLANCK_CAP_CAPSULE_GEOMETRY` is absent. For a registered client, these entries return `UNSUPPORTED`; RequestActorGeometry zeroes its request output and performs no queueing or physical mutation. Existing capsule observations are still copied as metadata.

Review identified a lifetime gap in the initial native geometry path: a queued raw body address could outlive entity removal or be reset before the adapter acquired world ownership. That executor and queue have been removed. The native adapter must not be reintroduced by merely checking `getWorld()` on a potentially dead address. A future implementation needs a qualified retained-object/lifetime-fence handoff or fresh live-body resolution with generation/revision validation protected by engine ownership, while preserving graph -> world ordering and never holding the registry mutex while waiting for an engine lock. PLANCK must remain the sole NPC physical owner, and PPB must supply fitting data rather than a second driver. This requested geometry role is unimplemented, not a delivered capability.

## Verification and remaining work

Run `python tests/run_synergy_tests.py --build-dir <external-directory>`. This compiles the actual production registry with a C11 consumer and tests lifecycle generations, coherent concurrent samples, load suspension, owner checks, callback reentrancy and drainage, hit decisions/results, 300 target-invalidation cycles during policy and fail-closed geometry requests. It also extracts the actual native clutter method and actor publisher into explicit fake engine tests. These verify veto/scale ordering, registry publication before world unlock, body destruction at unlock without stale republication, and publication observer dispatch after graph/world release.

The previous lifecycle and reset-only cleanup regression suites remain supported. Revision 001 hashes are verified. Full Release/x64 compilation was attempted on 2 November 2026 with deployment disabled, using installed SKSE VR include roots. The independent service translation unit compiled under the native project's forced prefix; other plugin units remain blocked by missing compatible Havok headers and nonportable SDK project references. No DLL was produced, installed or loaded, and no game was started. See [native prerequisites](native-build-prerequisites.md).

Remaining concept services include HIGGS endpoint/constraint coupling, correlated cross-provider physical operations, wider scoped weapon/interaction policies and all physical geometry adoption. This implementation does not claim those capabilities.
