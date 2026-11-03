# Native build and binding verification

Updated 2 November 2026. The complete native plugin now compiles and links with MSVC v145, the public SKSE VR2.00.12 source and compatible Havok2010.2.0-r1 declarations. This supersedes the earlier missing-header blocker. Source/core checks, native linking, PE metadata checks and actual Skyrim qualification remain different results. The current [implementation ledger](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-synergy/implementation-status.md) records the delivered checkpoint.

## External inputs

Supply the SKSE source root containing `common/` and `sksevr/`, a compatible Havok `Source/` tree and an external output directory. No game folder or installation step is required. The header dependency inspected for this build is the2010.2.0-r1 tree in [Nemesis at52543894](https://github.com/ShikyoKira/Project-New-Reign---Nemesis-Main/tree/52543894f060375151bd40012d55821b38b81bfc/external/hkxcmd/havok_2010_2_0/Source). It remains an external dependency with its own notices; none of those headers or libraries is distributed in this repository. The tooling does not download dependencies or grant a new licence to them.

[`build_sdk_support.py`](../tools/build_sdk_support.py) compiles the actual SKSE support sources into three x64 static-CRT libraries:14common units,4SKSE-common units and144runtime units. Its manifest records source hashes, commands, failures and resulting library hashes. The build does not invoke the SDK projects' deployment hooks or modify the original SDK.

```powershell
python tools/build_sdk_support.py --sdk-root <SKSE-source-root> --output <external-support-output>

python tools/build_native.py --sdk-root <SKSE-source-root> --havok-root <Havok-Source-root> --support-library <external-support-output>/sksevr_1_4_15.lib --support-library <external-support-output>/skse64_common.lib --support-library <external-support-output>/common_vc14.lib --output <external-plugin-output>

python tools/verify_native_bindings.py --native-build <external-plugin-output> --image <SkyrimVR.exe>
```

The first two commands use Python's standard library and an x64 MSVC installation. The separate metadata verifier requires `pefile`. Build outputs, dependency staging and manifests stay outside the source checkout. `--compile-only` is available for diagnosis; it does not establish a linked native DLL.

## Compatibility boundary

[`build_native.py`](../tools/build_native.py) reads the existing native project's source list instead of compiling a portable fixture in its place. It bypasses project references, author-specific library paths and post-build copy commands. The generated external SDK overlays expose the fields the existing reverse-engineered sources inspect, route the SDK's inline memory-router and heap accessors to the game's existing wrappers, and retain the explicit eight-field convex-build configuration as a plain aggregate. The overlays preserve data layout and virtual slots; before/after hashes are recorded. They are development declarations, not a second physics engine.

[`sdk_bindings.cpp`](../src/RE/sdk_bindings.cpp) supplies the missing SDK link boundary. Engine operations delegate to the game: reference ownership uses the existing add/remove bindings; rigid-body configuration uses the existing constructor binding; four base virtual implementations use the verified table targets below. SDK DLL-local TLS and allocator globals do not substitute for Skyrim's memory owners. Colour packing and SIMD numerical constants are pure local values.

| Binding | VR1.4.15 RVA | Static evidence |
|---|---:|---|
| `hkReferencedObject::getClassType` | `0xA01800` | `hkReferencedObject` vtable at`0x15DA7B8`, slot1 |
| `hkReferencedObject::calcContentStatistics` | `0xA01810` | Same table, slot2 |
| `hkpConstraintData::getSolverResults` | `0xACC460` | `hkpConstraintData` vtable at`0x17ADF48`, slot13 |
| `hkpConstraintData::addInstance` | `0xACC470` | Same table, slot14 |
| Rigid-body configuration construction | `0xAC5FE0` | Existing upstream typed relocation retained |
| Container heap and per-thread memory router | Existing upstream bindings | Existing game allocator and TLS lookup reused |

The verifier compares those four table entries in the selected image and checks executable target sections. A small standalone executable runs the actual SDK numerical code and compares all576bytes of enum-ordered constants with the game's read-only table at`0x177CF50`. It also checks colour packing, value-returning min/max compatibility and native DLL machine/entry-point metadata. It neither loads the plugin DLL nor executes Skyrim. The encrypted on-disk text does not establish instruction-level signatures; the evidence is table/layout/compiler evidence, with game behavior still unqualified.

## CommonLib preparation

The [canonical migration assessment and inventory](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-research/commonlib-assessment.md) separate existing CommonLib wrapper candidates, metadata-only matches and operations needing further audit or an extension. These temporary legacy-SDK bindings are candidates for that later library boundary. No CommonLib source or Address Library entry is changed by this build work. Actor/body generations, physical publication, policy ownership and hit decisions remain with PLANCK.
