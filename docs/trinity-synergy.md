# PLANCK architecture for VRIK HIGGS and PLANCK synergy

The proposed synergy gives Skyrim VR mods a shared foundation with clear owners. HIGGS brokers grip/trigger input and owns physical hand/item interactions. VRIK interprets hand position, maps anchors onto the actual player body/equipment, handles spatial interactions and renders. PLANCK owns NPC physical animation, ragdoll lifetime and physical-hit processing. Consumers keep their gameplay, inventory-selection and equipment-proxy rules.

A separate slot service, **Body Slots** as a working name, owns slot creation, stable definitions/instances, local placement and access geometry, generic allowed-content policies and saved customization. Its main workflow is an offline visual editor on a reference body/skeleton/equipment model → editable project and versioned declarative package → slot runtime/API → VRIK binding, hand detection, interaction and presentation. Authoring/export requires neither Skyrim nor VRIK. Keeping the native 14 holsters is an optional compatibility path. The editor and new services are proposals, not implemented features.

The only maintained source of the full concept and illustrative pseudo-ABI is [the English concept in Body Pouches](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-synergy/concept-en.md), with [a Russian counterpart](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-synergy/concept-ru.md). This file records PLANCK-specific requirements, not another copy of the concept. Body Pouches intends to adopt the architecture; it is not an available SDK or an agreement with the framework authors.

## Required architectural changes in PLANCK

1. **Expose copied NPC state and validated endpoints.** Provide actor, bone and body metadata, coordinate spaces and generations. Attachment requests return endpoints with a declared lifetime rather than private ragdoll pointers. Ragdoll replacement, actor unload, world replacement and game load invalidate dependent endpoints and constraints.

2. **Separate hit candidates from committed outcomes.** Offer a bounded policy stage before the relevant physical-hit commitment, followed by immutable results. Observing a candidate does not permit changing damage afterward. Define scope, conflict resolution and visible user priorities where alternatives are selectable; process each physical hit once.

3. **Replace global tuning with scoped policies.** Registered consumers request policies for their declared actor, weapon or interaction and owned leases for temporary effects. Weight, parry and penetration consumers keep their gameplay rules instead of changing unrelated weapons' thresholds or restoring another mod's settings.

4. **Use HIGGS for player-hand ownership and physical requests.** Migrate temporary hand restrictions to owned suppression leases; request explicit release when possession must end and await confirmed results. PLANCK drives NPC animation; HIGGS remains the final actuator for its player hand/weapon bodies. A penetration consumer decides wound/extraction rules, PLANCK validates the NPC endpoint and HIGGS applies the weapon constraint.

5. **Keep slot authoring and body-slot interaction outside PLANCK.** Body Slots owns definitions, generic eligibility and customization; VRIK owns actual body binding, hand detection and slot presentation. Taking an item from a slot uses VRIK/content-executor and HIGGS contracts; PLANCK participates when the resulting action interacts with NPC physics or its hit processing. It does not become a slot registry, inventory/equip executor or required provider for an offline editor, potion pouch, generic harvest or climb.

6. **Make lifecycle and safe phases part of the ABI.** Keep interface 001 and its hit-event contract unchanged. Negotiate additive capabilities with copied size-tagged records, request/executor identities, epochs and explicit callback lifetimes. Support removal with confirmed drainage and queue mutations at their legal phase. Slot binding generation, physical possession and NPC endpoint generation are distinct; never serialize live endpoint or lease handles.

The current [001 interface](../include/planckinterface001.h), [API implementation](../src/pluginapi.cpp) and [main runtime](../src/main.cpp) are refactoring starting points. Internal bug repairs and stability checks do not establish that the proposed ABI exists.

CommonLib is the second synergy level: reuse its current actor, scene, locking and Havok primitives, and move address handling and repeated technical operations into verified library methods. NPC policy, endpoints and hit commitment remain PLANCK runtime services; common engine code does not take over those decisions.
