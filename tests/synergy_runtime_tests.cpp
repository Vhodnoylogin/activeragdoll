#include "synergy_runtime.h"
#include <atomic>
#include <cassert>
#include <chrono>
#include <cmath>
#include <cstring>
#include <iostream>
#include <thread>
#include <type_traits>
#include <vector>
extern "C" int run_c_consumer(const PlanckSynergyAPI*);
using namespace PlanckSynergy;
const auto* api=GetAPI();
static_assert(std::is_standard_layout_v<PlanckHitSnapshot> && std::is_trivially_copyable_v<PlanckBodyPhysics>);
PlanckToken Client(const char* name){PlanckClientIdentity i{sizeof(i),0,{}};strcpy_s(i.id,name);PlanckToken c=0;assert(api->RegisterClient(&i,&c)==PLANCK_OK);return c;}
std::vector<BodySample> Bodies(uintptr_t first=100){
    std::vector<BodySample> b(2);
    for(size_t i=0;i<b.size();++i){b[i].identity=first+i;b[i].lineage=777;b[i].state.size=sizeof(PlanckBodyPhysics);b[i].state.capsule=1;b[i].state.capsuleRadius=.1f;b[i].state.capsuleB.z=.5f;b[i].state.worldRotation[3]=1;}
    return b;
}
void Publish(uintptr_t first=100){PublishActor(42,999,false,10,20,1.,Bodies(first));}
PlanckBodyPhysics Copy(PlanckToken c){PlanckActorPhysics a{sizeof(a)};PlanckBodyPhysics b[2]{};b[0].size=b[1].size=sizeof(b[0]);uint32_t count=0;assert(api->CopyActorPhysics(c,42,&a,b,2,&count)==PLANCK_OK);assert(count==2&&a.sample==b[0].sample&&a.sample==b[1].sample);return b[0];}
struct Events {PlanckToken client=0,sub=0;unsigned count=0;PlanckStatus removal=999;bool selfRemove=false,closeClient=false;};
void PLANCK_CALL Event(const PlanckEvent* e,void* p){auto& x=*static_cast<Events*>(p);++x.count;assert(e->size==sizeof(*e));if(x.selfRemove)x.removal=api->Unsubscribe(x.client,x.sub);if(x.closeClient)x.removal=api->ReleaseClient(x.client);}
void PLANCK_CALL Deny(const PlanckHitSnapshot* h,PlanckHitDecision* d,void* p){assert(h->outcome==PLANCK_HIT_PENDING);++*static_cast<unsigned*>(p);d->deny=1;}
void PLANCK_CALL Reduce(const PlanckHitSnapshot*,PlanckHitDecision* d,void*){d->damageScale=.25f;}
void PLANCK_CALL ResetPolicy(const PlanckHitSnapshot*,PlanckHitDecision*,void*){Reset();}
void PLANCK_CALL Malformed(const PlanckHitSnapshot*,PlanckHitDecision* d,void*){d->damageScale=NAN;}
PlanckGeometryRequest Geometry(PlanckBodyPhysics b){return {sizeof(PlanckGeometryRequest),0,b.body,b.geometryRevision,{0,0,0},{0,0,.6f},.12f,0};}
PlanckHitSnapshot Hit(uint32_t kind=PLANCK_HIT_CLUTTER){return BeginHit(kind,42,1,{},{},10.f,2,10,20);}
void Lifecycle(){
    Reset();Publish();assert(run_c_consumer(api)==1);
    auto a=Client("lifecycle.a"),b=Client("lifecycle.b");auto body=Copy(a);
    PlanckEndpointQuery q{sizeof(q),0,body.body,{0,0,.2f},0};PlanckEndpoint e{sizeof(e)};
    assert(api->AcquireAttachmentEndpoint(a,&q,&e)==PLANCK_OK);
    assert(api->ReleaseLease(b,e.lease)==PLANCK_INVALID);
    Events events{a};assert(api->Subscribe(a,PLANCK_ENDPOINT_INVALIDATED,Event,&events,&events.sub)==PLANCK_OK);
    Publish();assert(api->ValidateAttachmentEndpoint(a,e.lease,&e)==PLANCK_OK);
    Publish(200);assert(events.count==1&&api->ValidateAttachmentEndpoint(a,e.lease,&e)==PLANCK_STALE);
    auto replacement=Copy(a);assert(replacement.body.actor.actorGeneration!=body.body.actor.actorGeneration);
    assert(api->AcquireAttachmentEndpoint(a,&q,&e)==PLANCK_STALE);
    q.body=replacement.body;assert(api->AcquireAttachmentEndpoint(a,&q,&e)==PLANCK_OK);
    InvalidateBody(200);assert(events.count==2&&api->ValidateAttachmentEndpoint(a,e.lease,&e)==PLANCK_STALE);
    Publish();body=Copy(a);Reset();Publish();assert(Copy(a).body.actor.epoch!=body.body.actor.epoch);
    assert(api->ReleaseClient(a)==PLANCK_OK);assert(api->ReleaseClient(b)==PLANCK_OK);
}
void CoherentSnapshotsAndLoading(){
    Reset();Publish();auto c=Client("snapshots");std::atomic<bool> done=false;
    std::thread publisher([&]{for(unsigned i=0;i<1000;++i){auto bodies=Bodies();for(auto& b:bodies)b.state.worldPosition.x=static_cast<float>(i);PublishActor(42,999,false,i,20,1.,bodies);}done.store(true);});
    while(!done.load()){
        PlanckActorPhysics actor{sizeof(actor)};PlanckBodyPhysics bodies[2]{};bodies[0].size=bodies[1].size=sizeof(bodies[0]);uint32_t required=0;
        assert(api->CopyActorPhysics(c,42,&actor,bodies,2,&required)==PLANCK_OK);
        assert(bodies[0].sample==actor.sample&&bodies[1].sample==actor.sample&&bodies[0].worldPosition.x==bodies[1].worldPosition.x);
    }
    publisher.join();auto before=Copy(c);SetSuspended(true);Publish();PlanckActorPhysics actor{sizeof(actor)};uint32_t required=0;
    assert(api->CopyActorPhysics(c,42,&actor,nullptr,0,&required)==PLANCK_STALE);
    assert(Hit().outcome==PLANCK_HIT_CANCELLED);SetSuspended(false);Publish();assert(Copy(c).body.actor.epoch!=before.body.actor.epoch);
    assert(api->ReleaseClient(c)==PLANCK_OK);
}
void HitPolicies(){
    Reset();Publish();auto c=Client("hits");auto body=Copy(c);PlanckToken lease=0;
    PlanckActorPolicy scoped{sizeof(scoped),PLANCK_POLICY_SUPPRESS_HITS,body.body.actor,1.f,3};
    assert(api->RequestActorPolicy(c,&scoped,&lease)==PLANCK_OK);auto h=Hit();assert(h.outcome==PLANCK_HIT_DENIED);
    auto unrelated=BeginHit(PLANCK_HIT_CLUTTER,43,1,{},{},10.f,2,10,20);assert(unrelated.outcome==PLANCK_HIT_PENDING);FinishHit(unrelated.hitId,true);
    assert(api->ReleaseLease(c,lease)==PLANCK_OK);
    PlanckHitPolicy policy{sizeof(policy),3,{}};unsigned called=0;PlanckToken denial=0,reduction=0;
    assert(api->RegisterHitPolicy(c,&policy,Deny,&called,&denial)==PLANCK_OK);
    assert(api->RegisterHitPolicy(c,&policy,Reduce,nullptr,&reduction)==PLANCK_OK);
    h=Hit();assert(called==1&&h.outcome==PLANCK_HIT_DENIED&&h.damageScale==.25f);
    FinishHit(h.hitId,true);PlanckHitSnapshot result{sizeof(result)};assert(api->CopyHitSnapshot(c,h.hitId,&result)==PLANCK_OK&&result.outcome==PLANCK_HIT_DENIED);
    assert(api->Unsubscribe(c,denial)==PLANCK_OK);h=Hit();assert(h.outcome==PLANCK_HIT_PENDING&&h.damageScale==.25f);FinishHit(h.hitId,true);FinishHit(h.hitId,false);
    assert(api->CopyHitSnapshot(c,h.hitId,&result)==PLANCK_OK&&result.outcome==PLANCK_HIT_ALLOWED);
    h=Hit(PLANCK_HIT_MELEE);assert(h.damageScale==1.f);FinishHit(h.hitId,false);
    assert(api->Unsubscribe(c,reduction)==PLANCK_OK);
    PlanckToken malformed=0;assert(api->RegisterHitPolicy(c,&policy,Malformed,nullptr,&malformed)==PLANCK_OK);assert(Hit().outcome==PLANCK_HIT_DENIED);assert(Hit().outcome==PLANCK_HIT_PENDING); // bad policy retired
    PlanckToken reset=0;assert(api->RegisterHitPolicy(c,&policy,ResetPolicy,nullptr,&reset)==PLANCK_OK);assert(Hit().outcome==PLANCK_HIT_CANCELLED);
    assert(api->ReleaseClient(c)==PLANCK_OK);
}
void Drainage(){
    Reset();Publish();auto c=Client("drain.self");Events e{c};e.selfRemove=true;
    assert(api->Subscribe(c,PLANCK_ACTOR_CHANGED,Event,&e,&e.sub)==PLANCK_OK);
    InvalidateActor(42);assert(e.count==1&&e.removal==PLANCK_BUSY);Publish();assert(e.count==1);assert(api->Unsubscribe(c,e.sub)==PLANCK_OK);assert(api->ReleaseClient(c)==PLANCK_OK);
    c=Client("drain.client");Events closed{c};closed.closeClient=true;
    assert(api->Subscribe(c,PLANCK_RESET,Event,&closed,&closed.sub)==PLANCK_OK);Reset();assert(closed.count==1&&closed.removal==PLANCK_BUSY);Reset();assert(closed.count==1);assert(api->ReleaseClient(c)==PLANCK_OK);
    c=Client("drain.concurrent");std::atomic<bool> entered=false,leave=false;PlanckToken sub=0;
    struct Context {std::atomic<bool>* entered;std::atomic<bool>* leave;} context{&entered,&leave};
    auto callback=+[](const PlanckEvent*,void* p){auto& x=*static_cast<Context*>(p);x.entered->store(true);while(!x.leave->load())std::this_thread::yield();};
    assert(api->Subscribe(c,PLANCK_RESET,callback,&context,&sub)==PLANCK_OK);
    std::thread emitter([]{Reset();});while(!entered.load())std::this_thread::yield();
    assert(api->Unsubscribe(c,sub)==PLANCK_BUSY);leave.store(true);emitter.join();assert(api->Unsubscribe(c,sub)==PLANCK_OK);assert(api->ReleaseClient(c)==PLANCK_OK);
}
void GeometryRequests(){
    Reset();SetGeometryExecutorAvailable(false);Publish();auto c=Client("geometry");auto q=Geometry(Copy(c));PlanckToken request=999;
    assert(!(api->capabilities&PLANCK_CAP_CAPSULE_GEOMETRY));
    assert(api->RequestActorGeometry(c,&q,&request)==PLANCK_UNSUPPORTED&&request==0);
    SetGeometryExecutorAvailable(true);assert(api->capabilities&PLANCK_CAP_CAPSULE_GEOMETRY);
    auto degenerate=q;degenerate.capsuleB=degenerate.capsuleA;
    assert(api->RequestActorGeometry(c,&degenerate,&request)==PLANCK_INVALID&&request==0);
    assert(api->RequestActorGeometry(c,&q,&request)==PLANCK_OK&&request);
    PlanckToken other=0;assert(api->RequestActorGeometry(c,&q,&other)==PLANCK_CONFLICT);
    PlanckRequestResult result{sizeof(result)};
    assert(api->GetRequestResult(c,request,&result)==PLANCK_OK&&result.stage==PLANCK_REQUEST_ACCEPTED);
    unsigned called=0;
    auto execute=+[](PlanckToken id,const BodySample& body,const PlanckGeometryRequest& p,void* x){
        assert(id);
        assert(body.identity==100&&p.radius==.12f);++*static_cast<unsigned*>(x);return PlanckStatus(PLANCK_OK);
    };
    DeferredEvents deferred;ProcessActorGeometry(42,999,Bodies(),execute,&called,&deferred);
    assert(called==1&&Copy(c).capsuleRadius==.12f&&Copy(c).geometryRevision==2);
    assert(api->GetRequestResult(c,request,&result)==PLANCK_OK&&result.stage==PLANCK_REQUEST_COMPLETED&&result.geometryRevision==2);
    assert(api->CancelRequest(c,request)==PLANCK_OK);assert(api->ReleaseLease(c,request)==PLANCK_OK);
    assert(api->RequestActorGeometry(c,&q,&request)==PLANCK_STALE);
    q=Geometry(Copy(c));assert(api->RequestActorGeometry(c,&q,&request)==PLANCK_OK);
    assert(api->CancelRequest(c,request)==PLANCK_OK);
    ProcessActorGeometry(42,999,Bodies(),execute,&called,&deferred);assert(called==1);
    assert(api->GetRequestResult(c,request,&result)==PLANCK_OK&&result.stage==PLANCK_REQUEST_CANCELLED);
    assert(api->ReleaseLease(c,request)==PLANCK_OK);
    assert(api->RequestActorGeometry(c,&q,&request)==PLANCK_OK);InvalidateBody(100);Publish(200);
    assert(api->GetRequestResult(c,request,&result)==PLANCK_OK&&result.stage==PLANCK_REQUEST_CANCELLED);
    ProcessActorGeometry(42,999,Bodies(200),execute,&called,&deferred);assert(called==1);
    assert(api->ReleaseLease(c,request)==PLANCK_OK);
    q=Geometry(Copy(c));assert(api->RequestActorGeometry(c,&q,&request)==PLANCK_OK);
    auto pending=+[](PlanckToken,const BodySample&,const PlanckGeometryRequest&,void*){return NativeGeometryPending;};
    ProcessActorGeometry(42,999,Bodies(200),pending,nullptr,&deferred);
    assert(api->CancelRequest(c,request)==PLANCK_BUSY&&api->ReleaseLease(c,request)==PLANCK_BUSY);
    assert(api->ReleaseClient(c)==PLANCK_BUSY); // Closing cannot drop an admitted native request.
    const auto competing=Client("geometry.competing");PlanckToken competingRequest=999;
    assert(api->RequestActorGeometry(competing,&q,&competingRequest)==PLANCK_CONFLICT&&competingRequest==0);
    assert(api->ReleaseClient(competing)==PLANCK_OK);
    Reset();assert(api->ReleaseClient(c)==PLANCK_OK);
    SetGeometryExecutorAvailable(false);
}
PlanckStatus ResolveTest(PlanckToken c,PlanckToken lease,const PlanckEndpoint& e,PlanckEndpointVisitor visitor,void* context){
    PlanckNativeEndpoint n{};n.size=sizeof(n);n.rigidBody=100;n.world=888;n.endpoint=e;n.worldRotation[3]=1;
    return VisitResolvedEndpoint(c,lease,999,100,777,n,visitor,context);
}
void PhysicalBridge(){
    Reset();Publish();auto c=Client("native.bridge");auto body=Copy(c);PlanckEndpoint e{sizeof(e)};
    PlanckEndpointQuery q{sizeof(q),0,body.body,{0,0,.2f},0};
    assert(api->AcquireAttachmentEndpoint(c,&q,&e)==PLANCK_OK);
    const auto* bridge=GetPhysicalInteropAPI();assert(bridge->version==1&&bridge->size==16);
    auto visit=+[](const PlanckNativeEndpoint* n,void* value)->PlanckStatus{
        assert(n->rigidBody==100&&n->world==888&&n->endpoint.localPoint.z==.2f&&n->sample);
        ++*static_cast<unsigned*>(value);return PLANCK_OK;
    };
    unsigned calls=0;InstallNativeEndpointResolver(nullptr);
    assert(bridge->WithAttachmentEndpoint(c,e.lease,visit,&calls)==PLANCK_UNSUPPORTED);
    InstallNativeEndpointResolver(ResolveTest);
    assert(bridge->WithAttachmentEndpoint(c,e.lease,visit,&calls)==PLANCK_OK&&calls==1);
    auto release=+[](const PlanckNativeEndpoint*,void* value)->PlanckStatus{
        auto* pair=static_cast<PlanckToken*>(value);assert(api->ReleaseLease(pair[0],pair[1])==PLANCK_BUSY);
        assert(api->ReleaseClient(pair[0])==PLANCK_BUSY);return PLANCK_OK;
    };
    PlanckToken pair[2]{c,e.lease};assert(bridge->WithAttachmentEndpoint(c,e.lease,release,pair)==PLANCK_OK);
    assert(api->ReleaseClient(c)==PLANCK_OK);
    c=Client("native.bridge.stale");assert(api->AcquireAttachmentEndpoint(c,&q,&e)==PLANCK_OK);
    Publish(200);assert(bridge->WithAttachmentEndpoint(c,e.lease,visit,&calls)==PLANCK_STALE&&calls==1);
    assert(api->ReleaseClient(c)==PLANCK_OK);InstallNativeEndpointResolver(nullptr);
}
void PLANCK_CALL InvalidatePolicy(const PlanckHitSnapshot*,PlanckHitDecision*,void*){InvalidateActor(42);}
void InvalidationDuringPolicy(){
    Reset();Publish();auto c=Client("hits.invalidate");PlanckHitPolicy p{sizeof(p),3,{}};PlanckToken policy=0;
    Events terminal{c};assert(api->Subscribe(c,PLANCK_HIT_COMMITTED,Event,&terminal,&terminal.sub)==PLANCK_OK);
    assert(api->RegisterHitPolicy(c,&p,InvalidatePolicy,nullptr,&policy)==PLANCK_OK);
    // More than the retained hit pool: none may remain pending after cancellation.
    for(unsigned i=0;i<300;++i){
        Publish();auto h=Hit(PLANCK_HIT_MELEE);assert(h.hitId&&h.outcome==PLANCK_HIT_CANCELLED);
        PlanckHitSnapshot copied{sizeof(copied)};
        assert(api->CopyHitSnapshot(c,h.hitId,&copied)==PLANCK_OK&&copied.outcome==PLANCK_HIT_CANCELLED);
        assert(terminal.count==i+1);FinishHit(h.hitId,true);FinishHit(h.hitId,false);assert(terminal.count==i+1);
    }
    assert(api->Unsubscribe(c,policy)==PLANCK_OK);
    assert(api->RegisterHitPolicy(c,&p,ResetPolicy,nullptr,&policy)==PLANCK_OK);
    Publish();auto reset=Hit();assert(reset.hitId&&reset.outcome==PLANCK_HIT_CANCELLED);
    PlanckHitSnapshot copied{sizeof(copied)};
    assert(api->CopyHitSnapshot(c,reset.hitId,&copied)==PLANCK_NOT_FOUND);
    // Reset eviction must not resurrect an old epoch or emit an unqueryable hit.
    assert(terminal.count==300);FinishHit(reset.hitId,true);assert(terminal.count==300);
    assert(api->ReleaseClient(c)==PLANCK_OK);
}

int main(){Lifecycle();CoherentSnapshotsAndLoading();HitPolicies();Drainage();GeometryRequests();PhysicalBridge();InvalidationDuringPolicy();std::cout<<"PASS PLANCK production core, C consumer, lifecycle, coherent snapshots/loading, hit gates, geometry commitments, native endpoint bridge, cancellation interleavings and callback drainage\n";}
