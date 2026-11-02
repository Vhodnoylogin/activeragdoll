#pragma once
#include "planck_synergy.h"
#include <cstdint>
#include <vector>
namespace PlanckSynergy {
    struct BodySample { uintptr_t identity = 0, lineage = 0; PlanckBodyPhysics state{}; };
    // Native callers publish while holding graph -> world ownership. Stored
    // identities are comparison keys only; no native pointer is resolved here.
    struct DeferredEvent { uint32_t type; uint64_t subject; PlanckActorRef actor; uint32_t phase; };
    using DeferredEvents = std::vector<DeferredEvent>;
    const PlanckSynergyAPI* GetAPI();
    void PublishActor(uint32_t handle, uintptr_t modelIdentity, bool ragdolled,
        uint64_t frame, uint64_t tick, double time, const std::vector<BodySample>& bodies,
        DeferredEvents* deferred = nullptr);
    void InvalidateActor(uint32_t handle, DeferredEvents* deferred = nullptr);
    void DispatchEvents(const DeferredEvents& deferred);
    void InvalidateBody(uintptr_t identity);
    void Reset();
    void SetSuspended(bool suspended);
    PlanckHitSnapshot BeginHit(uint32_t kind, uint32_t target, uint32_t source,
        PlanckVec3 position, PlanckVec3 velocity, float damage, uint32_t hand,
        uint64_t frame, uint64_t tick);
    // Called exactly once by a successful native commitment or cancellation path.
    void FinishHit(uint64_t hitId, bool committed);
}
