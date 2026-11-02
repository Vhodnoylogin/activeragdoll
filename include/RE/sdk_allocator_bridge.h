#pragma once

class hkMemoryRouter;
class hkMemoryAllocator;

// Used only by the generated external SDK overlay. The game owns the router and
// allocator; SDK DLL-local TLS or allocator globals must never replace them.
hkMemoryRouter& hkGetMemoryRouter();
hkMemoryAllocator& SkyrimGetContainerHeapAllocator();
