#include "synergy_runtime.h"
#include <algorithm>
#include <chrono>
#include <cmath>
#include <cstring>
#include <deque>
#include <limits>
#include <map>
#include <memory>
#include <mutex>
#include <string>

namespace PlanckSynergy {
namespace {
constexpr size_t MaxClients=64, MaxResources=512, MaxBodies=256, MaxActors=512, MaxHits=256;
constexpr uint64_t EventMask=63;
struct Client { std::string id; bool closing=false; };
struct ActorState { uintptr_t model=0; PlanckActorPhysics state{}; std::vector<BodySample> bodies; };
enum class Kind { Subscription, Endpoint, ActorPolicy, HitPolicy };
struct Resource {
    Kind kind{}; PlanckToken owner=0; bool active=true; uint32_t inFlight=0;
    uint64_t mask=0; PlanckEventCallback event=nullptr; PlanckHitPolicyCallback hit=nullptr;
    void* context=nullptr;
    PlanckEndpoint endpoint{}; PlanckActorPolicy actorPolicy{}; PlanckHitPolicy hitPolicy{};
};
struct Registry {
    std::mutex lock;
    uint64_t epoch=1, serial=1, sample=0, eventSequence=0;
    bool exhausted=false, suspended=false;
    std::map<PlanckToken,Client> clients;
    std::map<uint32_t,ActorState> actors;
    std::map<PlanckToken,std::shared_ptr<Resource>> resources;
    std::map<uint64_t,PlanckHitSnapshot> hits;
    std::deque<uint64_t> hitOrder;
    PlanckToken Next() {
        if (exhausted || serial==(std::numeric_limits<uint64_t>::max)()) { exhausted=true; return 0; }
        return serial++;
    }
};
Registry& State() { static Registry value; return value; }
thread_local uint32_t callbackDepth=0;
thread_local uint64_t threadToken=0;
uint64_t ThreadToken(Registry& registry){if(!threadToken)threadToken=registry.Next();return threadToken;}
struct CallbackScope { CallbackScope(){++callbackDepth;} ~CallbackScope(){--callbackDepth;} };
template<class T> bool Sized(const T* value) { return value && value->size>=sizeof(T); }
bool Finite(PlanckVec3 v) { return std::isfinite(v.x)&&std::isfinite(v.y)&&std::isfinite(v.z); }
bool Scale(float value) { return std::isfinite(value)&&value>=0.f&&value<=1.f; }
bool Same(PlanckActorRef a,PlanckActorRef b) { return a.epoch==b.epoch&&a.actorGeneration==b.actorGeneration&&a.handle==b.handle; }
bool Same(PlanckBodyRef a,PlanckBodyRef b) { return Same(a.actor,b.actor)&&a.bodyGeneration==b.bodyGeneration&&a.index==b.index; }
PlanckStatus ClientStatus(Registry& r,PlanckToken client,bool closing=false) {
    auto it=r.clients.find(client);
    return it==r.clients.end()?PLANCK_INVALID:(!closing&&it->second.closing?PLANCK_BUSY:PLANCK_OK);
}
BodySample* FindBody(Registry& r,PlanckBodyRef ref) {
    if(r.suspended)return nullptr;
    auto it=r.actors.find(ref.actor.handle);
    if (it==r.actors.end()||!Same(it->second.state.actor,ref.actor)||ref.index>=it->second.bodies.size()) return nullptr;
    auto& body=it->second.bodies[ref.index];
    return Same(body.state.body,ref)?&body:nullptr;
}
bool CurrentActor(Registry& r,PlanckActorRef actor) {
    if(r.suspended)return false;
    auto it=r.actors.find(actor.handle);
    return it!=r.actors.end()&&Same(actor,it->second.state.actor);
}
std::shared_ptr<Resource> Owned(Registry& r,PlanckToken owner,PlanckToken id) {
    auto it=r.resources.find(id);
    return it!=r.resources.end()&&it->second->owner==owner?it->second:nullptr;
}
void Emit(uint32_t type,uint64_t subject,PlanckActorRef actor,uint32_t phase) {
    auto& r=State(); std::vector<PlanckToken> callbacks; PlanckEvent ev{};
    {
        std::lock_guard guard(r.lock);
        ev={sizeof(ev),type,++r.eventSequence,r.epoch,subject,actor,phase,0,ThreadToken(r)};
        for(auto& [id,res]:r.resources) if(res->kind==Kind::Subscription&&res->active&&(res->mask&type)) callbacks.push_back(id);
    }
    // The engine owns lifecycle dispatch; recursive client emission is unavailable.
    // A malicious/internal recursive engine call is bounded, and never holds this lock.
    if(callbackDepth>=8) return;
    for(auto id:callbacks) {
        std::shared_ptr<Resource> res;
        {
            std::lock_guard guard(r.lock); auto it=r.resources.find(id);
            if(it==r.resources.end()||!it->second->active) continue;
            res=it->second; ++res->inFlight;
        }
        bool failed=false;
        { CallbackScope scope; auto copy=ev; try {res->event(&copy,res->context);} catch(...) {failed=true;} }
        { std::lock_guard guard(r.lock); --res->inFlight; if(failed)res->active=false; }
    }
}
void RetireActorLocked(Registry& r,PlanckActorRef actor,std::vector<uint64_t>& endpoints) {
    for(auto& [id,res]:r.resources) {
        if(res->kind==Kind::Endpoint&&Same(res->endpoint.body.actor,actor)&&res->active) {res->active=false;endpoints.push_back(id);}
        if(res->kind==Kind::ActorPolicy&&Same(res->actorPolicy.actor,actor)) res->active=false;
    }
}
PlanckStatus RegisterClient(const PlanckClientIdentity* info,PlanckToken* output) {
    if(output)*output=0;
    if(!Sized(info)||!output||info->reserved||!info->id[0]||!std::memchr(info->id,0,sizeof(info->id)))return PLANCK_INVALID;
    if(callbackDepth)return PLANCK_REENTRANT;
    auto& r=State();std::lock_guard guard(r.lock);
    if(r.clients.size()>=MaxClients)return PLANCK_LIMIT;
    for(auto& [id,c]:r.clients)if(c.id==info->id)return PLANCK_CONFLICT;
    auto id=r.Next();if(!id)return PLANCK_LIMIT;
    r.clients.emplace(id,Client{info->id,false});*output=id;return PLANCK_OK;
}
PlanckStatus ReleaseClient(PlanckToken owner) {
    auto& r=State();std::lock_guard guard(r.lock);
    auto status=ClientStatus(r,owner,true);if(status)return status;
    r.clients.at(owner).closing=true;
    bool busy=false;
    for(auto& [id,res]:r.resources)if(res->owner==owner){res->active=false;busy|=res->inFlight!=0;}
    if(busy)return PLANCK_BUSY; // Call again; no later callback may start.
    std::erase_if(r.resources,[owner](auto& pair){return pair.second->owner==owner;});
    r.clients.erase(owner);return PLANCK_OK;
}
PlanckStatus Subscribe(PlanckToken owner,uint64_t mask,PlanckEventCallback callback,void* context,PlanckToken* output) {
    if(output)*output=0;
    if(!output||!callback||!mask||(mask&~EventMask))return PLANCK_INVALID;
    if(callbackDepth)return PLANCK_REENTRANT;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    if(r.resources.size()>=MaxResources)return PLANCK_LIMIT;
    auto id=r.Next();if(!id)return PLANCK_LIMIT;
    auto res=std::make_shared<Resource>();res->kind=Kind::Subscription;res->owner=owner;res->mask=mask;res->event=callback;res->context=context;
    r.resources.emplace(id,res);*output=id;return PLANCK_OK;
}
PlanckStatus Unsubscribe(PlanckToken owner,PlanckToken id) {
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner,true);if(status)return status;
    auto res=Owned(r,owner,id);if(!res||(res->kind!=Kind::Subscription&&res->kind!=Kind::HitPolicy))return PLANCK_INVALID;
    res->active=false;if(res->inFlight)return PLANCK_BUSY;
    r.resources.erase(id);return PLANCK_OK;
}
PlanckStatus CopyActorPhysics(PlanckToken owner,uint32_t actor,PlanckActorPhysics* output,PlanckBodyPhysics* bodies,uint32_t capacity,uint32_t* required) {
    if(!Sized(output)||!required||(capacity&&!bodies))return PLANCK_INVALID;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    if(r.suspended)return PLANCK_STALE;
    auto it=r.actors.find(actor);if(it==r.actors.end())return PLANCK_NOT_FOUND;
    *required=static_cast<uint32_t>(it->second.bodies.size());
    if(capacity<*required)return PLANCK_BUFFER;
    for(uint32_t i=0;i<*required;++i)if(!Sized(&bodies[i]))return PLANCK_INVALID;
    *output=it->second.state;
    for(uint32_t i=0;i<*required;++i)bodies[i]=it->second.bodies[i].state;
    return PLANCK_OK;
}
PlanckStatus AcquireEndpoint(PlanckToken owner,const PlanckEndpointQuery* query,PlanckEndpoint* output) {
    if(!Sized(query)||!Sized(output)||query->reserved||query->reserved2||!Finite(query->localPoint))return PLANCK_INVALID;
    if(callbackDepth)return PLANCK_REENTRANT;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    if(!FindBody(r,query->body))return PLANCK_STALE;
    if(r.resources.size()>=MaxResources)return PLANCK_LIMIT;
    auto id=r.Next();if(!id)return PLANCK_LIMIT;
    auto res=std::make_shared<Resource>();res->kind=Kind::Endpoint;res->owner=owner;
    res->endpoint={sizeof(PlanckEndpoint),0,id,query->body,query->localPoint,0};
    r.resources.emplace(id,res);*output=res->endpoint;return PLANCK_OK;
}
PlanckStatus ValidateEndpoint(PlanckToken owner,PlanckToken id,PlanckEndpoint* output) {
    if(!Sized(output))return PLANCK_INVALID;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    auto res=Owned(r,owner,id);if(!res||res->kind!=Kind::Endpoint)return PLANCK_INVALID;
    if(!res->active||!FindBody(r,res->endpoint.body))return PLANCK_STALE;
    *output=res->endpoint;return PLANCK_OK;
}
PlanckStatus ReleaseLease(PlanckToken owner,PlanckToken id) {
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner,true);if(status)return status;
    auto res=Owned(r,owner,id);if(!res||(res->kind!=Kind::Endpoint&&res->kind!=Kind::ActorPolicy))return PLANCK_INVALID;
    if(res->inFlight)return PLANCK_BUSY;
    r.resources.erase(id);return PLANCK_OK;
}
PlanckStatus RequestPolicy(PlanckToken owner,const PlanckActorPolicy* policy,PlanckToken* output) {
    if(output)*output=0;
    if(!Sized(policy)||!output||(policy->flags&~PLANCK_POLICY_SUPPRESS_HITS)||!Scale(policy->damageScale)||!policy->hitKinds||(policy->hitKinds&~3u))return PLANCK_INVALID;
    if(callbackDepth)return PLANCK_REENTRANT;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    if(!CurrentActor(r,policy->actor))return PLANCK_STALE;
    if(r.resources.size()>=MaxResources)return PLANCK_LIMIT;
    auto id=r.Next();if(!id)return PLANCK_LIMIT;
    auto res=std::make_shared<Resource>();res->kind=Kind::ActorPolicy;res->owner=owner;res->actorPolicy=*policy;
    r.resources.emplace(id,res);*output=id;return PLANCK_OK;
}
PlanckStatus RegisterHitPolicy(PlanckToken owner,const PlanckHitPolicy* policy,PlanckHitPolicyCallback callback,void* context,PlanckToken* output) {
    if(output)*output=0;
    if(!Sized(policy)||!output||!callback||!policy->hitKinds||(policy->hitKinds&~3u))return PLANCK_INVALID;
    if(callbackDepth)return PLANCK_REENTRANT;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    if(policy->actor.handle&&!CurrentActor(r,policy->actor))return PLANCK_STALE;
    size_t count=0;for(auto& [id,res]:r.resources)if(res->kind==Kind::HitPolicy)++count;
    if(count>=16||r.resources.size()>=MaxResources)return PLANCK_LIMIT;
    auto id=r.Next();if(!id)return PLANCK_LIMIT;
    auto res=std::make_shared<Resource>();res->kind=Kind::HitPolicy;res->owner=owner;res->hitPolicy=*policy;res->hit=callback;res->context=context;
    r.resources.emplace(id,res);*output=id;return PLANCK_OK;
}
PlanckStatus CopyHit(PlanckToken owner,uint64_t id,PlanckHitSnapshot* output) {
    if(!Sized(output))return PLANCK_INVALID;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    auto it=r.hits.find(id);if(it==r.hits.end())return PLANCK_NOT_FOUND;
    *output=it->second;return PLANCK_OK;
}
PlanckStatus RequestGeometry(PlanckToken owner,const PlanckGeometryRequest* proposal,PlanckToken* output) {
    if(output)*output=0;
    if(!Sized(proposal)||!output)return PLANCK_INVALID;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner);if(status)return status;
    // No native lifetime-safe geometry executor is installed. Keep this reserved
    // table entry fail closed; in particular, never retain a raw body work item.
    return PLANCK_UNSUPPORTED;
}
PlanckStatus GetResult(PlanckToken owner,PlanckToken,PlanckRequestResult* output) {
    if(!Sized(output))return PLANCK_INVALID;
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner,true);if(status)return status;
    return PLANCK_UNSUPPORTED;
}
PlanckStatus CancelRequest(PlanckToken owner,PlanckToken) {
    auto& r=State();std::lock_guard guard(r.lock);auto status=ClientStatus(r,owner,true);if(status)return status;
    return PLANCK_UNSUPPORTED;
}
// All C entry points contain allocation/implementation exceptions. Callback errors
// are isolated separately, outside the registry lock.
template<auto Fn> struct Boundary;
template<class R,class... A,R(*Fn)(A...)> struct Boundary<Fn> {
    static R PLANCK_CALL Call(A... args) noexcept {try{return Fn(args...);}catch(...){return PLANCK_LIMIT;}}
};
const PlanckSynergyAPI api={sizeof(PlanckSynergyAPI),2,15,
    Boundary<RegisterClient>::Call,Boundary<ReleaseClient>::Call,Boundary<Subscribe>::Call,Boundary<Unsubscribe>::Call,
    Boundary<CopyActorPhysics>::Call,Boundary<AcquireEndpoint>::Call,Boundary<ValidateEndpoint>::Call,
    Boundary<ReleaseLease>::Call,Boundary<RequestPolicy>::Call,Boundary<RegisterHitPolicy>::Call,Boundary<CopyHit>::Call,
    Boundary<RequestGeometry>::Call,Boundary<GetResult>::Call,Boundary<CancelRequest>::Call};
}
const PlanckSynergyAPI* GetAPI(){return &api;}

void PublishActor(uint32_t handle,uintptr_t model,bool ragdolled,uint64_t frame,uint64_t tick,double time,const std::vector<BodySample>& bodies,DeferredEvents* deferred) {
    if(!handle)return;
    if(!model||bodies.empty()||bodies.size()>MaxBodies){InvalidateActor(handle,deferred);return;}
    auto& r=State();std::vector<uint64_t> invalidated;PlanckActorRef old{},current{};bool changed=false;
    {
        std::lock_guard guard(r.lock);
        if(r.suspended||r.exhausted)return;
        if(!r.actors.contains(handle)&&r.actors.size()>=MaxActors)return;
        auto it=r.actors.find(handle);
        bool replaced=it==r.actors.end()||it->second.model!=model||it->second.bodies.size()!=bodies.size();
        if(!replaced)for(size_t i=0;i<bodies.size();++i)if(it->second.bodies[i].identity!=bodies[i].identity||it->second.bodies[i].lineage!=bodies[i].lineage){replaced=true;break;}
        ActorState next;next.model=model;next.bodies=bodies;
        const auto sample=++r.sample;
        if(replaced) {
            changed=true;
            if(it!=r.actors.end()){old=it->second.state.actor;RetireActorLocked(r,old,invalidated);}
            const auto generation=r.Next();if(!generation)return;
            current={r.epoch,generation,handle,0};
            for(size_t i=0;i<bodies.size();++i) {
                auto generationBody=r.Next();if(!generationBody)return;
                next.bodies[i].state.body={current,generationBody,static_cast<uint32_t>(i),0};
                next.bodies[i].state.geometryRevision=1;
            }
        }else{
            current=it->second.state.actor;changed=it->second.state.ragdolled!=static_cast<uint32_t>(ragdolled);
            for(size_t i=0;i<bodies.size();++i){
                next.bodies[i].state.body=it->second.bodies[i].state.body;
                auto& before=it->second.bodies[i].state;auto& after=next.bodies[i].state;
                const bool geometryChanged=before.capsule!=after.capsule||before.capsuleRadius!=after.capsuleRadius||
                    std::memcmp(&before.capsuleA,&after.capsuleA,sizeof(PlanckVec3))||std::memcmp(&before.capsuleB,&after.capsuleB,sizeof(PlanckVec3));
                after.geometryRevision=before.geometryRevision+(geometryChanged?1:0);
            }
        }
        for(auto& b:next.bodies){b.state.size=sizeof(b.state);b.state.sample=sample;b.state.boneName[95]=0;}
        next.state={sizeof(PlanckActorPhysics),static_cast<uint32_t>(bodies.size()),current,sample,frame,tick,time,PLANCK_PHASE_MAIN,static_cast<uint32_t>(ragdolled)};
        r.actors[handle]=std::move(next);
    }
    DeferredEvents events;
    for(auto id:invalidated)events.push_back({PLANCK_ENDPOINT_INVALIDATED,id,old,PLANCK_PHASE_MAIN});
    if(changed)events.push_back({PLANCK_ACTOR_CHANGED,0,current,PLANCK_PHASE_MAIN});
    if(deferred)deferred->insert(deferred->end(),events.begin(),events.end());else DispatchEvents(events);
}
void DispatchEvents(const DeferredEvents& events){for(const auto& event:events)Emit(event.type,event.subject,event.actor,event.phase);}
void InvalidateActor(uint32_t handle,DeferredEvents* deferred){
    auto& r=State();PlanckActorRef old{};std::vector<uint64_t> endpoints;
    {std::lock_guard guard(r.lock);auto it=r.actors.find(handle);if(it==r.actors.end())return;old=it->second.state.actor;RetireActorLocked(r,old,endpoints);r.actors.erase(it);}
    DeferredEvents events;
    for(auto id:endpoints)events.push_back({PLANCK_ENDPOINT_INVALIDATED,id,old,PLANCK_PHASE_LIFECYCLE});
    events.push_back({PLANCK_ACTOR_CHANGED,0,old,PLANCK_PHASE_LIFECYCLE});
    if(deferred)deferred->insert(deferred->end(),events.begin(),events.end());else DispatchEvents(events);
}
void InvalidateBody(uintptr_t identity){
    auto& r=State();std::vector<uint32_t> handles;
    {std::lock_guard guard(r.lock);for(auto& [handle,actor]:r.actors)for(auto& body:actor.bodies)if(body.identity==identity){handles.push_back(handle);break;}}
    for(auto handle:handles)InvalidateActor(handle);
}
void Reset(){
    auto& r=State();std::vector<std::pair<uint64_t,PlanckActorRef>> endpoints;
    {std::lock_guard guard(r.lock);
        if(r.epoch==(std::numeric_limits<uint64_t>::max)())r.exhausted=true;else ++r.epoch;
        for(auto& [id,res]:r.resources){
            if(res->kind==Kind::Endpoint&&res->active)endpoints.emplace_back(id,res->endpoint.body.actor);
            if(res->kind==Kind::Endpoint||res->kind==Kind::ActorPolicy)res->active=false;
        }
        r.actors.clear();r.hits.clear();r.hitOrder.clear();
    }
    for(auto [id,actor]:endpoints)Emit(PLANCK_ENDPOINT_INVALIDATED,id,actor,PLANCK_PHASE_LIFECYCLE);
    Emit(PLANCK_RESET,0,{},PLANCK_PHASE_LIFECYCLE);
}
void SetSuspended(bool suspended){
    {auto& r=State();std::lock_guard guard(r.lock);r.suspended=suspended;}
    if(suspended)Reset();
}
PlanckHitSnapshot BeginHit(uint32_t kind,uint32_t target,uint32_t source,PlanckVec3 position,PlanckVec3 velocity,float damage,uint32_t hand,uint64_t frame,uint64_t tick){
    PlanckHitSnapshot hit{sizeof(PlanckHitSnapshot),kind,0,0,frame,tick,{},source,PLANCK_HIT_CANCELLED,position,velocity,damage,1.f,hand,PLANCK_PHASE_HIT,0};
    if(callbackDepth||!target||!(kind==PLANCK_HIT_MELEE||kind==PLANCK_HIT_CLUTTER))return hit;
    auto& r=State();std::vector<PlanckToken> policies;bool denied=false;
    {
        std::lock_guard guard(r.lock);if(r.suspended)return hit;hit.hitId=r.Next();if(!hit.hitId)return hit;hit.threadId=ThreadToken(r);hit.epoch=r.epoch;hit.target={r.epoch,0,target,0};
        auto actor=r.actors.find(target);if(actor!=r.actors.end())hit.target=actor->second.state.actor;
        hit.outcome=PLANCK_HIT_PENDING;
        for(auto& [id,res]:r.resources)if(res->active){
            if(res->kind==Kind::ActorPolicy&&(res->actorPolicy.hitKinds&kind)&&Same(res->actorPolicy.actor,hit.target)){
                denied|=(res->actorPolicy.flags&PLANCK_POLICY_SUPPRESS_HITS)!=0;
                if(kind==PLANCK_HIT_CLUTTER)hit.damageScale=(std::min)(hit.damageScale,res->actorPolicy.damageScale);
            }
            if(res->kind==Kind::HitPolicy&&(res->hitPolicy.hitKinds&kind)&&(!res->hitPolicy.actor.handle||Same(res->hitPolicy.actor,hit.target)))policies.push_back(id);
        }
        // Do not evict an in-flight commitment; nested engine hits are bounded.
        if(r.hits.size()>=MaxHits){
            auto victim=std::find_if(r.hitOrder.begin(),r.hitOrder.end(),[&](auto id){return r.hits.at(id).outcome!=PLANCK_HIT_PENDING;});
            if(victim==r.hitOrder.end()){hit.hitId=0;hit.outcome=PLANCK_HIT_CANCELLED;return hit;}
            r.hits.erase(*victim);r.hitOrder.erase(victim);
        }
        r.hits.emplace(hit.hitId,hit);r.hitOrder.push_back(hit.hitId);
    }
    Emit(PLANCK_HIT_CANDIDATE,hit.hitId,hit.target,PLANCK_PHASE_HIT);
    const auto start=std::chrono::steady_clock::now();
    for(auto id:policies){
        if(std::chrono::steady_clock::now()-start>std::chrono::milliseconds(2)){denied=true;break;}
        std::shared_ptr<Resource> res;
        {std::lock_guard guard(r.lock);auto it=r.resources.find(id);if(it==r.resources.end()||!it->second->active||r.epoch!=hit.epoch)continue;res=it->second;++res->inFlight;}
        PlanckHitDecision decision{sizeof(decision),0,1.f,0};bool failed=false;
        const auto before=std::chrono::steady_clock::now();
        {CallbackScope scope;auto copy=hit;try{res->hit(&copy,&decision,res->context);}catch(...){failed=true;}}
        failed|=std::chrono::steady_clock::now()-before>std::chrono::milliseconds(1);
        failed|=decision.size!=sizeof(decision)||decision.deny>1||decision.reserved||!Scale(decision.damageScale);
        {std::lock_guard guard(r.lock);--res->inFlight;if(failed)res->active=false;}
        denied|=failed||decision.deny;
        if(!failed&&kind==PLANCK_HIT_CLUTTER)hit.damageScale=(std::min)(hit.damageScale,decision.damageScale);
    }
    bool terminal=false;
    {
        std::lock_guard guard(r.lock);
        if(r.epoch!=hit.epoch||(hit.target.actorGeneration&&!CurrentActor(r,hit.target))||!r.hits.contains(hit.hitId)){
            hit.outcome=PLANCK_HIT_CANCELLED;
            // Target removal can occur during a policy callback. Retire the
            // stored pending snapshot too, even when the caller returns early.
            // Reset may already have evicted it; never recreate that old epoch.
            auto stored=r.hits.find(hit.hitId);
            if(stored!=r.hits.end()&&stored->second.outcome==PLANCK_HIT_PENDING){stored->second=hit;terminal=true;}
        } else {
            // Pending until FinishHit: observers cannot turn this into a commitment.
            hit.outcome=denied?PLANCK_HIT_DENIED:PLANCK_HIT_PENDING;r.hits[hit.hitId]=hit;
            terminal=denied;
        }
    }
    if(terminal)Emit(PLANCK_HIT_COMMITTED,hit.hitId,hit.target,PLANCK_PHASE_HIT);
    return hit;
}
void FinishHit(uint64_t id,bool committed){
    if(!id)return;auto& r=State();PlanckActorRef actor{};
    {std::lock_guard guard(r.lock);auto it=r.hits.find(id);if(it==r.hits.end()||it->second.outcome!=PLANCK_HIT_PENDING)return;
        it->second.outcome=committed?PLANCK_HIT_ALLOWED:PLANCK_HIT_CANCELLED;actor=it->second.target;}
    Emit(PLANCK_HIT_COMMITTED,id,actor,PLANCK_PHASE_HIT);
}
}
