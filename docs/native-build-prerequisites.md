# Native build prerequisites

Checked on 11 October 2026. The production plugin remains unbuilt and unqualified in Skyrim. Standalone source/ABI fixtures exercise the delivered repairs without establishing native hook or Havok layout compatibility. The current [implementation ledger](https://github.com/Vhodnoylogin/body-pouches/blob/main/docs/trinity-synergy/implementation-status.md) records that boundary.

## Available dependencies and configuration work

MSVC toolset `v145` and Windows SDK `10.0.26100.0` are installed. Original SKSE VR `2.00.12` source, `common/IPrefix.h`, SKSE support sources, Xbyak and OpenVR headers also exist outside this checkout. The earlier missing-prefix/SKSE-project failures are caused by the authored project layout; they do not establish that the SDK is unavailable.

The [native project](../activeragdoll.vcxproj) targets Release/x64, C++20 and the static CRT. It expects sibling `../skse64/skse64.vcxproj` and `../skse64_common/skse64_common.vcxproj`, a parent include root containing `common/`, and an absolute author-specific Havok include directory. These paths do not resolve in the current independent checkout. The original SDK requires both its `src` and `src/sksevr` include roots. Its default SKSE Release target is a DLL; static support uses `Release_Lib` variants or separately compiled required SDK units. A future build definition must reconcile those targets, runtime/toolset settings, libraries and external paths. Disabling project-reference builds alone does not supply their link symbols.

## Remaining header prerequisite

The source directly includes 40 distinct Havok-style paths. Mandatory examples include `Common/Base/hkBase.h`, `Physics/Dynamics/Entity/hkpRigidBody.h`, `Physics/Collide/Shape/Convex/Box/hkpBoxShape.h` and `Physics/Utilities/Collide/TriggerVolume/hkpTriggerVolume.h`. PLANCK additionally requires animation ragdoll, rigid-body controller, skeleton mapper and behavior/controller definitions.

The required compatible include tree is absent from the audited workspace and the project's authored directory. A bounded workspace search found no `hkBase.h`; rigid-body matches were CommonLib-modeled `RE/...` headers, rather than the paths requested by this project. This is a bounded location check, not a claim about every possible source or every file on the machine. The exact definitions and layout assertions must be qualified before accepting a complete native build. The project does not explicitly name a Havok library; further linker requirements remain unproven until compilation can proceed.

## Isolated build boundary

The plugin has a post-build DLL copy into the game directory. SKSE dependency projects also have copy hooks, including some static-library configurations. Any future isolated build must disable post-build events globally with `/p:PostBuildEventUseInBuild=false`, set external `OutDir` and `IntDir`, and check the dependency targets. Read-only project-property evaluation did not invoke those targets or deploy anything.

The next build step is to provide the compatible header dependency and configure explicit external SDK paths/static support targets, then compile the actual plugin and qualify hooks/layouts. No native build definition, dependency replacement or CommonLib implementation is delivered by this prerequisite analysis.
