#pragma once
// Private reset-only fence for deferred non-ragdoll collision cleanup.
// No engine objects, callbacks, public API or actor-lifetime authority.
#include <cstdint>
#include <limits>
#include <mutex>

namespace PlanckCleanup {
    struct Ticket { std::uint64_t generation = 0; };
    struct State { std::uint64_t generation = 1; bool exhausted = false; };

    inline State Next(const State& previous) noexcept {
        State candidate = previous;
        if (!candidate.exhausted) {
            if (candidate.generation == (std::numeric_limits<std::uint64_t>::max)()) candidate.exhausted = true;
            else ++candidate.generation;
        }
        return candidate;
    }

    class Epoch final {
    public:
        Ticket Capture() const {
            std::scoped_lock lock(mutex_);
            return state_.exhausted ? Ticket{} : Ticket{state_.generation};
        }
        bool IsCurrent(Ticket ticket) const {
            std::scoped_lock lock(mutex_);
            return !state_.exhausted && ticket.generation && ticket.generation == state_.generation;
        }
        void Invalidate() {
            std::scoped_lock lock(mutex_);
            Commit(Next(state_));
        }
    private:
        void Commit(State candidate) noexcept { state_ = candidate; }
        mutable std::mutex mutex_;
        State state_;
    };

    inline Epoch& Owner() { static Epoch owner; return owner; }
    inline Ticket Capture() { return Owner().Capture(); }
    inline bool IsCurrent(Ticket ticket) { return Owner().IsCurrent(ticket); }
    inline void Invalidate() { Owner().Invalidate(); }
}
