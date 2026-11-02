#include "planck_synergy.h"
#include "planck_physical_interop.h"
#include "planck_compound_api.h"
#include <assert.h>
#include <stddef.h>
#include <string.h>
_Static_assert(sizeof(PlanckPhysicalInteropAPI)==16,"native bridge table");
_Static_assert(sizeof(PlanckNativeEndpoint)==144,"native borrowed endpoint ABI");
_Static_assert(sizeof(PlanckToken)==8,"64 bit handles");
_Static_assert(sizeof(PlanckVec3)==12,"vector POD layout");
_Static_assert(sizeof(PlanckActorRef)==24,"actor ABI");
_Static_assert(sizeof(PlanckBodyRef)==40,"body ABI");
_Static_assert(sizeof(PlanckActorPhysics)==72,"actor snapshot ABI");
_Static_assert(sizeof(PlanckBodyPhysics)==216,"body snapshot ABI");
_Static_assert(sizeof(PlanckHitSnapshot)==120,"hit snapshot ABI");
_Static_assert(sizeof(PlanckEvent)==72,"event ABI");
_Static_assert(sizeof(PlanckGeometryRequest)==88,"geometry ABI");
_Static_assert(offsetof(PlanckSynergyAPI,RegisterClient)==16,"table prefix");
_Static_assert(sizeof(PlanckSynergyAPI)==128,"x64 revision2 table");
_Static_assert(sizeof(PlanckCompoundGeometryAPI)==32,"compound table ABI");
_Static_assert(sizeof(PlanckBodyGeometry)==72,"compound view ABI");
_Static_assert(sizeof(PlanckShapeChild)==56,"child view ABI");
_Static_assert(sizeof(PlanckCapsuleEdit)==40,"child proposal ABI");
_Static_assert(sizeof(PlanckCompoundProposal)==64,"compound proposal ABI");
int run_c_consumer(const PlanckSynergyAPI* api) {
    PlanckClientIdentity identity={sizeof(identity),0,"planck.test.c"};
    PlanckToken client=0,first=0;
    PlanckActorPhysics actor={0};
    PlanckBodyPhysics bodies[2]={{0}};
    PlanckEndpointQuery query={0};
    PlanckEndpoint endpoint={0};
    uint32_t required=0;
    assert(api && api->size>=sizeof(*api) && api->version==2);
    assert(api->RegisterClient(&identity,&client)==PLANCK_OK && client);
    first=client;
    assert(api->RegisterClient(&identity,&client)==PLANCK_CONFLICT);
    /* RegisterClient zeroes failed outputs; use a fresh identity for the owner. */
    memcpy(identity.id,"planck.test.c.2",sizeof("planck.test.c.2"));
    assert(api->RegisterClient(&identity,&client)==PLANCK_OK);
    actor.size=sizeof(actor);
    assert(api->CopyActorPhysics(client,42,&actor,0,0,&required)==PLANCK_BUFFER && required==2);
    bodies[0].size=bodies[1].size=sizeof(bodies[0]);
    assert(api->CopyActorPhysics(client,42,&actor,bodies,2,&required)==PLANCK_OK);
    assert(actor.sample==bodies[0].sample && actor.sample==bodies[1].sample);
    query.size=sizeof(query);query.body=bodies[0].body;query.localPoint.z=.1f;
    endpoint.size=sizeof(endpoint);
    assert(api->AcquireAttachmentEndpoint(client,&query,&endpoint)==PLANCK_OK);
    assert(api->ValidateAttachmentEndpoint(client,endpoint.lease,&endpoint)==PLANCK_OK);
    assert(api->ReleaseLease(client,endpoint.lease)==PLANCK_OK);
    assert(api->ReleaseClient(client)==PLANCK_OK);
    assert(api->ReleaseClient(first)==PLANCK_OK);
    return 1;
}
