#include "RE/offsets.h"
#include <Common/Base/Types/Color/hkColor.h>

// Link the legacy SDK declarations to the game's implementation. These are VR
// 1.4.15 bindings, not SDK substitute implementations. See the migration ledger.
const hkClass* hkReferencedObject::getClassType() const
{
    using Fn = const hkClass* (*)(const hkReferencedObject*);
    static RelocAddr<Fn> function(0xA01800);
    return function(this);
}

void hkReferencedObject::addReference() const
{
    hkReferencedObject_addReference(const_cast<hkReferencedObject*>(this));
}

void hkReferencedObject::removeReference() const
{
    hkReferencedObject_removeReference(const_cast<hkReferencedObject*>(this));
}

void hkReferencedObject::calcContentStatistics(hkStatisticsCollector* collector, const hkClass* type) const
{
    using Fn = void (*)(const hkReferencedObject*, hkStatisticsCollector*, const hkClass*);
    static RelocAddr<Fn> function(0xA01810);
    function(this, collector, type);
}

hkpSolverResults* hkpConstraintData::getSolverResults(hkpConstraintRuntime* runtime)
{
    using Fn = hkpSolverResults* (*)(hkpConstraintData*, hkpConstraintRuntime*);
    static RelocAddr<Fn> function(0xACC460);
    return function(this, runtime);
}

void hkpConstraintData::addInstance(hkpConstraintInstance* constraint, hkpConstraintRuntime* runtime, int bytes) const
{
    using Fn = void (*)(const hkpConstraintData*, hkpConstraintInstance*, hkpConstraintRuntime*, int);
    static RelocAddr<Fn> function(0xACC470);
    function(this, constraint, runtime, bytes);
}

hkpRigidBodyCinfo::hkpRigidBodyCinfo()
{
    hkpRigidBodyCinfo_ctor(this);
}

hkMemoryAllocator& SkyrimGetContainerHeapAllocator()
{
    return *g_hkContainerHeapAllocator;
}

int HK_CALL hkColor::rgbFromChars(unsigned char r, unsigned char g, unsigned char b, unsigned char a)
{
    return static_cast<int>((static_cast<unsigned>(a) << 24) |
        (static_cast<unsigned>(r) << 16) | (static_cast<unsigned>(g) << 8) | b);
}

// Mathematical constants, independently encoded in SDK enum order. All 576
// bytes match the game's read-only table at RVA0x177CF50 in the pinned image.
// No game pointer is dereferenced during DLL static initialization.
const hkQuadReal hkQuadRealHalf = _mm_set1_ps(0.5f);
const hkQuadReal hkQuadReal3333 = _mm_set1_ps(3.0f);
const hkQuadReal hkQuadReal0000 = _mm_setzero_ps();
const hkQuadReal hkQuadRealMinusHalf = _mm_set1_ps(-0.5f);
const hkQuadReal g_vectorConstants[HK_QUADREAL_END] = {
    _mm_set1_ps(-1.f), _mm_setzero_ps(), _mm_set1_ps(1.f),
    _mm_set1_ps(2.f), _mm_set1_ps(3.f), _mm_set1_ps(4.f),
    _mm_set1_ps(5.f), _mm_set1_ps(6.f), _mm_set1_ps(7.f),
    _mm_set1_ps(15.f), _mm_set1_ps(16.f), _mm_set1_ps(255.f),
    _mm_set1_ps(256.f), _mm_set1_ps(8388608.f), _mm_setzero_ps(),
    _mm_set1_ps(1.f), _mm_set1_ps(0.5f), _mm_set1_ps(1.f / 3.f),
    _mm_set1_ps(0.25f), _mm_set1_ps(0.2f), _mm_set1_ps(1.f / 6.f),
    _mm_set1_ps(1.f / 7.f), _mm_set1_ps(1.f / 15.f), _mm_set1_ps(1.f / 255.f),
    _mm_setr_ps(1.f, 0.f, 0.f, 0.f), _mm_setr_ps(0.f, 1.f, 0.f, 0.f),
    _mm_setr_ps(0.f, 0.f, 1.f, 0.f), _mm_setr_ps(0.f, 0.f, 0.f, 1.f),
    _mm_set1_ps(3.402820018375656e38f), _mm_set1_ps(1.1920928955078125e-7f),
    _mm_set1_ps(1.4210854715202004e-14f), _mm_setr_ps(-1.f, 1.f, -1.f, 1.f),
    _mm_setr_ps(8.f, 4.f, 2.f, 1.f), _mm_set1_ps(1.00390625f),
    _mm_set1_ps(1966080000.f), _mm_set1_ps(5.086263077380693e-10f)
};

static_assert(HK_QUADREAL_END == 36);
static_assert(sizeof(hkpRigidBody) == 0x2D0);
static_assert(sizeof(hkpConstraintData) == 0x18);
static_assert(sizeof(hkpConvexVerticesShape::BuildConfig) == 0x18);
static_assert(offsetof(hkpConvexVerticesShape::BuildConfig, m_convexRadius) == 4);
static_assert(offsetof(hkpConvexVerticesShape::BuildConfig, m_maxCosAngleForBevelPlanes) == 0x14);
