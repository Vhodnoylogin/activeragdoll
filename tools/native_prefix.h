#pragma once

// Include the SDK's movie definition before its callbacks use the complete type.
#include "common/IPrefix.h"
#include "skse64/ScaleformMovie.h"
#include <algorithm>

// Legacy sources called the Windows macros without qualification. NOMINMAX
// keeps new service code usable; these ordinary functions evaluate once.
template <class A, class B>
constexpr auto min(A a, B b)
{
    return a < b ? a : b;
}

template <class A, class B>
constexpr auto max(A a, B b)
{
    return a > b ? a : b;
}
