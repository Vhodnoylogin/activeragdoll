# PLANCK architecture for VRIK HIGGS and PLANCK synergy

The proposed synergy gives Skyrim VR mods a shared foundation with clear owners:
VRIK provides the player body, spatial hand interpretation and generic zones/slots;
HIGGS brokers controller input and owns physical hand/item interactions; PLANCK
owns NPC physical animation, ragdoll lifetime and its physical-hit processing.
Consumers retain their gameplay and request services from those owners.

The single source of the full concept, including illustrative pseudo-ABI, is
[the English concept in Body Pouches](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-synergy/concept-en.md).
[The Russian version](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-synergy/concept-ru.md)
is maintained in the same directory. Body Pouches intends to adopt this
architecture. The services below are proposed changes, not an available SDK or
an agreement with the framework authors.

## Required architectural changes in PLANCK

1. **Expose NPC physics through copied state and validated endpoints.** Provide
   actor, bone and body metadata, coordinate spaces and generations. An attachment
   request returns an endpoint with a defined lifetime, rather than encouraging
   consumers to retain private ragdoll pointers. Ragdoll replacement, actor unload,
   world replacement and game load invalidate dependent endpoints and constraints.

2. **Separate physical-hit candidates from committed outcomes.** Offer a bounded,
   documented policy stage before PLANCK commits the relevant hit, followed by
   immutable result events. An observed candidate is not permission to change
   damage afterward. Define scope, conflict resolution and user priorities where
   alternative policies are selectable; process a physical hit once.

3. **Replace per-mod global tuning with scoped interaction policies.** Give a
   registered consumer a policy for its declared actor, weapon or interaction and
   an owned lease for temporary effects. Weight, parry and penetration providers
   keep their gameplay rules. They should not need to change global thresholds
   for unrelated weapons or restore another consumer's settings.

4. **Use HIGGS services for player-hand ownership and physical requests.** Migrate
   temporary hand restrictions to owned HIGGS suppression leases and use explicit
   release requests when possession must end. Wait for confirmed results before
   dependent operations. PLANCK drives NPC physical animation; HIGGS remains the
   final actuator for its player hand/weapon bodies. A penetration mod decides
   wound and extraction rules, PLANCK validates the NPC endpoint, and HIGGS applies
   the corresponding weapon constraint.

5. **Make lifecycle and safe phases part of the ABI.** Keep interface 001 and its
   existing hit-event contract unchanged. Negotiate additive capabilities with
   copied, size-tagged records, request/executor identities, epochs and explicit
   callback lifetimes. Support removal with confirmed drainage and queue mutations
   for their legal physics phase. Do not serialize live endpoint or lease handles.

The current [001 interface](../include/planckinterface001.h),
[API implementation](../src/pluginapi.cpp) and [main runtime](../src/main.cpp)
provide the existing hit data, settings and HIGGS hand calls. They are starting
points for this refactoring. Internal bug repairs and stability work remain
separate source/build/runtime checks, not evidence that the new ABI exists.

Reuse CommonLib for verified actor, scene, locking and Havok operations. NPC policy
and endpoint ownership remain PLANCK runtime services. Generic harvesting and
climbing do not require PLANCK unless they actually interact with its NPC domain.
