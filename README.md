# PLANCK ([Nexus link](https://www.nexusmods.com/skyrimspecialedition/mods/66025))

## Cooperation development

`main` preserves the upstream source; `development` contains the consolidated fork work and [PLANCK-specific synergy requirements](docs/trinity-synergy.md). The only maintained full concept and implementation ledger are in [Body Pouches](https://github.com/Vhodnoylogin/body-pouches/tree/main/docs/trinity-synergy). PLANCK owns NPC physics and hit processing; HIGGS owns hand states/use and input, VRIK supplies body/virtual-hand pose, PPB supplies anatomical surfaces/touch evidence, and Body Slots owns all slot mechanics.

## Proposed cooperation with VRIK HIGGS and PLANCK

This fork's intended direction follows the concept maintained only in Body Pouches. The source API below implements a bounded part of PLANCK's role; the remaining contracts and qualification limits are explicit. This is not an agreement with the framework authors or a game-qualified release.

The [native build procedure](docs/native-build-prerequisites.md) builds the complete DLL from external SDK inputs without deployment hooks and verifies its binding metadata. Native linking now succeeds; game qualification remains pending.

This mod is also complicated.

The development branch includes bounded lifecycle repairs for temporary NPC
movement/look-at restrictions and nested hit-event context. Run their source-backed
standalone checks with `python tests/run_lifecycle_regressions.py --build-dir <external-directory>`.
The [regression fixture](tests/README.md) uses a fake engine; the separately linked native plugin remains untested in game.

`development` also implements an additive [plain-C cooperation API](docs/synergy-api.md)
with copied actor/body samples, validated endpoint descriptors, owned policies and
removable callbacks, precommit physical-hit decisions, safe-phase cloned capsule geometry adoption and
a separate scoped native endpoint bridge for HIGGS. Revision 001 is unchanged. The actual service and selected native adapters
have standalone CPU fixtures; HIGGS constraint transport and native/game qualification
remain outstanding. The branch merges upstream 0.8.2 at `aed524a`.

A private [reset-only deferred cleanup fence](docs/deferred-cleanup.md) also prevents
queued furniture/get-up collision cleanup from adopting a replacement graph after
reset. Its actual-source CPU fixture is `tests/run_cleanup_epoch_tests.py`; it adds
no actor endpoint or complete physics-lifetime guarantee.

To build from source, it requires object definitions / headers similar to those belonging to havok 2010.2. I will not be providing these, nor do I claim to have them myself.


PLANCK has a C++ API that can be used by other mods.\
To use it, copy `src/planckinterface001.cpp` and `include/planckinterface001.h` into your project.\
Then, do something like this in your SKSE plugin in `PostPostLoad` or later (this is important - if you try and get the interface before `PostPostLoad`, such as in `PostLoad`, it will not work).

```cpp
#include "planckinterface001.h"

...

void OnSKSEMessage(SKSEMessagingInterface::Message* msg)
{
  if (msg) {
    if (msg->type == SKSEMessagingInterface::kMessage_PostPostLoad) {
      // Get the PLANCK plugin API
      PlanckPluginAPI::GetPlanckInterface001(g_pluginHandle, g_messaging);
      if (g_planckInterface) {
        _MESSAGE("Got planck interface!");
        unsigned int planckVersion = g_planckInterface->GetBuildNumber();
      }
    }
  }
}
```
To receive hit events with extended info provided by PLANCK, you do not need to fetch the interface (though there is no harm in it).\
Planck hit events are simply extensions to regular hit events. When receiving a hit event within a regular hit event handler, check if it's a hit from planck and then simply treat it as a planck hit event, like so.
```cpp
class HitEventHandler : public BSTEventSink <TESHitEvent>
{
public:
  virtual EventResult ReceiveEvent(TESHitEvent *evn, EventDispatcher<TESHitEvent> *dispatcher)
  {
    PlayerCharacter *player = *g_thePlayer;
    if (evn->caster == player) {
      if (PlanckPluginAPI::IsPlanckHit(evn)) {
        PlanckPluginAPI::PlanckHitEvent *extendedEvent = (PlanckPluginAPI::PlanckHitEvent *)evn;
        _MESSAGE("%s", extendedEvent->extendedHitData.nodeName);
      }
    }
    return kEvent_Continue;
  }
};
```
