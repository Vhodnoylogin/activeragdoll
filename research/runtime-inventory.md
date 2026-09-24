# PLANCK — инвентарь времени выполнения

Теги: planck, higgs, vrik, хуки, havok, коллизии, ragdoll, синергия, исследование

Ветка исследования: `research/trinity-synergy` (HEAD `f06fc95`, версия 0.8.1 — `include/version.h`).
Все ссылки `путь:строка` даны от корня репозитория PLANCK (`D:\Skyrim VR Modding\PLANCK`), если не
указано иное. Ссылки на HIGGS — от корня `D:\Skyrim VR Modding\HIGGS`. Выводы, не подтверждённые
строкой кода, помечены **[вывод]**.

Имена ресурсов даны с приставками общего словаря (`hook:`, `patch:`, `node:`, `havok:`, `collision:`,
`setting:`, `input:`, `form:`, `event:`, `papyrus:`, `api:`, `equip:`, `anim:`, `haptics:`, `frame:`),
чтобы таблицы трёх модов можно было соединить.

## 0. Какая DLL на самом деле работает в сборке

| факт | доказательство | как проверить |
|---|---|---|
| В сборке включены два мода с `SKSE\Plugins\activeragdoll.dll`; побеждает **PLANCK VR Lifetime and Collision Alpha Fix** (prio 918) над оригиналом (prio 919) | вывод индекса | `python wt-claude-projects/claude-skyrim-vr/index/idx.py conflicts "SKSE\Plugins\activeragdoll.dll"` |
| Победившая DLL — сборка «PLANCK VR Stability Patch 1.3.0» на базе 0.8.1 + PR 3, 5, 6 чужого форка, без PR 4, плюс перепривязка костей анимационного графа при подмене узла оружия | `mods\PLANCK VR Lifetime and Collision Alpha Fix\Source\DOWNSTREAM_PATCH.md:1-44` | — |
| Набор хуков и адресов в исходнике этой сборки **совпадает** с нашим клоном | сравнение `Write5Call/Write6Call/Write5Branch/Write6Branch/SafeWrite64/SafeWriteBuf` и `RelocAddr/RelocPtr(0x…)` в `src/main.cpp` обоих деревьев — различий нет | `diff` по grep, см. команду в журнале чата |
| Единственная добавка сборки к записи в движок — перезапись указателей `graph->boneNodes.entries` при подмене узла | `mods\PLANCK VR Lifetime and Collision Alpha Fix\Source\src\main.cpp:7365` | — |
| Ini, реально читаемый движком: `activeragdoll.ini` из мода PLANCK (патч-мод ini не несёт) | `src/config.cpp:624`; список файлов патч-мода без ini | `idx.py owns "activeragdoll.ini"` |

Значит, инвентарь ниже описывает установленную сборку; все условные хуки в ней **включены** —
`forceGenerateForActiveRagdolls=1`, `doClutterVsBipedCollisionDamage=1`,
`dontResetPitchRollWhenGettingUp=1`, `dontRemoveRagdollWhenDoneGettingUp=1`,
`seamlessFurnitureTransition=1`, `disableCullingForActiveRagdolls=1`
(`mods\PLANCK - Physical Animation and Character Kinetics\SKSE\Plugins\activeragdoll.ini:544,552,614,622,570,542`).

## 1. Установка хуков

- Хуки ставятся из `SKSEPlugin_Load` → `TryHook()` → `PerformHooks()` (`src/main.cpp:8332`, `7940-7976`, `7522-7938`),
  остальные vtable-правки — прямо в `SKSEPlugin_Load` (`src/main.cpp:8354-8385`).
- Трамплины берутся у SKSE: 1024 байта ветвлений и 1024 байта кодогенерации (`src/main.cpp:7943-7960`).
- `Write5Call` — своя обёртка: читает текущее смещение `call` и возвращает прежнюю цель, поэтому хуки
  на один и тот же `call` **цепляются** за чужие, если те поставлены раньше (`src/main.cpp:7511-7520`).
- Часть хуков ставится через `g_branchTrampoline.Write5Call/Write6Call` **без сохранения оригинала** —
  такой хук заменяет вызов целиком (`src/main.cpp:7530`, `7564`, `7815`).

### 1.1. Хуки на место вызова (call-site, `E8 rel32` → своя функция)

| ресурс | адрес | что перехвачено и что делает PLANCK | условие | доказательство |
|---|---|---|---|---|
| `hook:call@0x6497E4 ProcessHavokHitJobs` | 0x6497E4 | **главная точка кадра PLANCK**: вызывает оригинал, затем всё обновление (см. §2, F5) | всегда | `src/main.cpp:7459`, `7525`, `4340-4822` |
| `hook:call@0x6ABCA4 PlayerCharacter::UpdateWeaponSwing` | 0x6ABCA4 | **замена без оригинала**: своя детекция взмаха по скорости контроллера для обеих рук | всегда | `src/main.cpp:7461`, `7530`, `4027-4031`, `1254-1312` |
| `hook:call@0xB1CB55 BShkbAnimationGraph::PreGenerate` | 0xB1CB55 | для активных актёров `updateData->forceUpdate=true` — граф генерируется каждый кадр без пропусков | `forceGenerateForActiveRagdolls` | `src/main.cpp:7473`, `7533-7536`, `5718-5726` |
| `hook:call@0xB266AB hkbRagdollDriver::driveToPose` | 0xB266AB | обёртка Pre/Post: правка дорожек генератора, ослабление констрейнтов, гравитация, варп, стресс | всегда | `src/main.cpp:7465`, `7538-7541`, `5690-5697`, `4886-5573` |
| `hook:call@0xB268DC hkbRagdollDriver::postPhysics` | 0xB268DC | обёртка Pre/Post: снимок анимационной и ragdoll-позы, смешивание (Blender), возврат гравитации | всегда | `src/main.cpp:7463`, `7543-7546`, `5700-5705`, `5577-5687` |
| `hook:call@0x61F6E7 Actor::TakePhysicsDamage` | 0x61F6E7 | глушит физический урон движка для активных актёров (PLANCK считает свой) | `doClutterVsBipedCollisionDamage` | `src/main.cpp:7475`, `7548-7551`, `5729-5734` |
| `hook:call@0x60C808 Actor::KillEndHavokHit` | 0x60C808 | при смерти возвращает гравитацию ragdoll-телам | всегда | `src/main.cpp:7479`, `7553-7556`, `5737-5747` |
| `hook:call@0x631CA7 Character::HitTarget→HitData::populate` | 0x631CA7 | ставит бит 30 `HitData.flags` для ударов PLANCK, запоминает «смертельность» (бит 0x20); ветка «физического блока» мертва (`IsPhysicallyBlocked` всегда `false`) | всегда | `src/main.cpp:7485`, `7558-7561`, `5846-5881` |
| `hook:call@0x687164 Actor::IsRagdollMovingSlowEnoughToGetUp` | 0x687164 | запрет вставания, пока тело держит HIGGS; сброс таймера нокдауна и высоты падения | всегда | `src/main.cpp:7491`, `7567-7570`, `6051-6081` |
| `hook:call@0x68727D GetUpEnd→RemoveRagdollFromWorld` | 0x68727D | для активных актёров не убирает ragdoll из мира после вставания | `dontRemoveRagdollWhenDoneGettingUp` | `src/main.cpp:7496`, `7582-7584`, `6084-6103` |
| `hook:call@0x6872D0 GetUpEnd→NiNode::SetMotionType(keyframed)` | 0x6872D0 | для активных актёров не переводит тела в keyframed | то же | `src/main.cpp:7497`, `7586-7587`, `6106-6112` |
| `hook:call@0x74D816 GetUpEndHandler→QueueRemoveCollisionFromWorld` | 0x74D816 | вместо снятия коллизии — задача «убрать не-ragdoll тела» | то же | `src/main.cpp:7498`, `7589-7590`, `6115-6125` |
| `hook:call@0xA2921E extractRagdollPoseInternal→computeReferenceFrame` | 0xA2921E | плавное вхождение вычисляемого worldFromModel (lerp «липкого» кадра) | всегда | `src/main.cpp:7500`, `7593-7596`, `6128-6146` |
| `hook:call@0xB51008 getApproxWorldFromBoneTransformAt→approxTransformAt` | 0xB51008 | применяет обратный rigidBodyT при чтении тел ragdoll | `applyRigidBodyTWhenReadingRigidBodies` (проверка внутри) | `src/main.cpp:7502`, `7598-7601`, `6149-6163` |
| `hook:call@0xA374B6 MapRagdollPoseToAnimPoseModelSpace→mapPose #1` | 0xA374B6 | подмена `ConstraintSource` на `NO_CONSTRAINTS` | `dontRestrictBoneLengthsWhenMappingFromRagdollToAnim` (внутри) | `src/main.cpp:7504`, `7603-7605`, `6167-6172` |
| `hook:call@0xA37533 MapRagdollPoseToAnimPoseModelSpace→mapPose #2` | 0xA37533 | то же | то же | `src/main.cpp:7506`, `7607-7608`, `6175-6180` |
| `hook:call@0xA28005 mapHighResPoseLocalToLowResPoseLocal→mapPose` | 0xA28005 | то же для направления anim→ragdoll | `dontRestrictBoneLengthsWhenMappingFromAnimToRagdoll` (внутри) | `src/main.cpp:7508`, `7611-7614`, `6183-6187` |
| `hook:call@0xA26C05 hkbRagdollDriver::driveToPose→hkaRagdollRigidBodyController::driveToPose` | 0xA26C05 | применяет rigidBodyT к позе и **извлекает стресс** в свой буфер `g_stressOut` (движок передаёт 0) | всегда | `src/main.cpp:7467`, `7616-7619`, `6190-6199`, `3079` |
| `hook:call@0x5BF24F bhkCollisionFilter::SetFromBGSCollisionLayers` | 0x5BF24F | после загрузки слоёв запоминает исходные битовые поля Biped/BipedNoCC | всегда | `src/main.cpp:6203`, `7621-7624`, `6204-6211` |
| `hook:call@0x703367 UpdateRagdollPostPhysics→Actor::UpdateFromCharacterControllerAndFootIK` | 0x703367 | принудительное обновление наклона/крена контроллера персонажа | `enableForcedOrientationUpdate` (внутри) | `src/main.cpp:6215`, `7626-7629`, `6216-6230` |
| `hook:call@0x5E0885 Actor::CheckAndHandleMotionOrAnimationDrivenChange` | 0x5E0885 | перевод схваченного NPC в motion-driven / Planner Direct Control и расчёт цели движения | всегда | `src/main.cpp:6440`, `7641-7644`, `6441-6776` |
| `hook:call@0x116D362 MovementPlannerArbiter→ActorState::CalculateSpeedsWithAcceleration` | 0x116D362 | подмена параметров ускорения для схваченного NPC | `grabbedActorMovementOverwriteParams` (внутри) | `src/main.cpp:6810`, `7646-7649`, `6811-6822` |
| `hook:call@0x116D39D MovementPlannerArbiter→ActorState::CalculateRotSpeeds` | 0x116D39D | то же для скорости поворота | то же | `src/main.cpp:6826`, `7651-7654`, `6827-6838` |
| `hook:call@0xA88B6A hkbBehaviorGraph::update→hkbUtils::collectActiveNodesLeafFirst` | 0xA88B6A | ищет в активных состояниях переход по `moveStart`; снимает `ignoreEvents` с `BSCyclicBlendTransitionGenerator` | всегда | `src/main.cpp:6843`, `7656-7659`, `6844-6909` |
| `hook:call@0xA55AC1 hkbStateMachine::requestTransitions→beginTransition` | 0xA55AC1 | сбрасывает `selfTransitionMode` в CONTINUE у переходов в циклическое смешивание | `forceContinueSelfTransitionForCyclicBlends` (внутри) | `src/main.cpp:6928`, `7666-7669`, `6929-6957` |
| `hook:call@0xBA3B36 hkaKeyFrameHierarchyUtility::CalculateApplyKeyframeData` | 0xBA3B36 | своя реализация с непрерывным slerp | `doContinuousSlerp` (внутри; в сборке `=0`) | `src/main.cpp:6390`, `7671-7674`, `6391-6408`; ini `:383` |
| `hook:call@0x3AFD84 bhkLinearCaster::linearCast→hkpWorld::linearCast` | 0x3AFD84 | для слоя Ground группы игрока выкидывает из коллекторов попадания по актёрам из `g_dontCollideActors` | всегда | `src/main.cpp:7345`, `7686-7689`, `7347-7378` |
| `hook:call@0x9CE8D0 Papyrus GetAnimationVariableBool→vfunc 0x12` | 0x9CE8D0 | **`Write6Call` без оригинала**: для игрока подменяет `bAllowRotation` и `IsBashing` во время силового взмаха/удара щитом | `spoofbAllowRotationDuringSwing`, `spoofIsBashingDuringSwing` (внутри) | `src/main.cpp:7489`, `7563-7565`, `5911-5937` |
| `hook:call@0x687FF7 ExitFurniture→QueueRemoveCollisionFromWorld` | 0x687FF7 | **`Write5Call` без оригинала**: для активных актёров вместо снятия коллизии — задача «убрать не-ragdoll тела» | `seamlessFurnitureTransition` | `src/main.cpp:7481`, `7813-7816`, `5803-5813` |
| `hook:call@0x1323E3E DoColorPass→NiCamera::FinishAccumulatingPostResolveDepth` | 0x1323E3E | отладочная отрисовка | только `_DEBUG` | `src/main.cpp:7432`, `8381-8386` |

### 1.2. Врезки через Xbyak (`jmp` на кодогенерированный переходник)

| ресурс | адрес | что делает | условие | доказательство |
|---|---|---|---|---|
| `hook:branch@0x636742 ScriptEventSourceHolder::DispatchHitEventFromHitData→DispatchHitEvent` | 0x636742 | подмена отправки `TESHitEvent`: удар PLANCK уходит расширенным `PlanckHitEvent` с магическим числом во флагах; физический урон PLANCK подставляет форму ударившего предмета | всегда | `src/main.cpp:7487`, `7696-7721`, `5883-5908` |
| `hook:entry@0x74B340 WeaponRightSwingHandler::Handle` | 0x74B340 | `Write6Branch` в пролог функции (прямо, мимо vtable — SKSE сам зовёт её напрямую); для игрока возвращает сразу, глуша звук взмаха движка | всегда | `src/RE/offsets.cpp:398`, `src/main.cpp:7723-7766`, `5940-5951` |
| `hook:entry@0x74B3D0 WeaponLeftSwingHandler::Handle` | 0x74B3D0 | то же для левой | всегда | `src/RE/offsets.cpp:399`, `src/main.cpp:7768-7811`, `5954-5965` |
| `hook:branch@0x688061 ExitFurniture→BSAnimationGraphManager::ResetRagdoll` | 0x688061 | для активных актёров не сбрасывает ragdoll, а выключает моторы констрейнтов на кадр | `seamlessFurnitureTransition` | `src/main.cpp:7482`, `7818-7843`, `5815-5829` |
| `hook:branch@0x68E344 EnterFurniture→BSAnimationGraphManager::SetWorld` | 0x68E344 | для активных актёров не обнуляет мир графа, а через 0,1 с ставит задачу «убрать не-ragdoll тела» | то же | `src/main.cpp:7483`, `7845-7870`, `5831-5844` |
| `hook:branch@0x5E086F Character::MovementControllerUpdate` | 0x5E086F | перед обновлением контроллера движения исполняет очередь толчков (`BumpActor`) | всегда | `src/main.cpp:7477`, `7873-7898`, `5749-5766` |
| `hook:branch@0x69F4B9 PreCullActors` | 0x69F4B9 | активным актёрам пишет `unk274 & 0xF = 7` — «не отсекать» | `disableCullingForActiveRagdolls` | `src/main.cpp:7471`, `7900-7932`, `5707-5715` |

### 1.3. Записи в vtable (`SafeWrite64`)

| ресурс | адрес слота | что делает | доказательство |
|---|---|---|---|
| `hook:vtbl@0x16D76C0 Character::ModifyMovementData` | 0x16D76C0 | ограничение сближения NPC с игроком после толчка; прямой поворот схваченного NPC (без strafe) | `src/main.cpp:6235`, `7631-7634`, `6236-6321` |
| `hook:vtbl@0x16D6E60 Character::InitLoadGame` | 0x16D6E60 | при загрузке снимает своё влияние с актёра до `FinishLoadGame` | `src/main.cpp:6413`, `7636-7639`, `6414-6423` |
| `hook:vtbl@0x17C5518 BSCyclicBlendTransitionGenerator::handleEvent` | 0x17C5518 | разрешает CyclicFreeze из состояния CrossBlend | `src/main.cpp:6913`, `7661-7664`, `6914-6924` |
| `hook:vtbl@0x17C68F0 BSLookAtModifier::modify` | 0x17C68F0 | снимок позы до LookAt для активных актёров; временно гасит `lookAtTarget` для «прижатых» к игроку | `src/main.cpp:7221`, `7676-7679`, `7222-7263` |
| `hook:vtbl@0x16E2580 PlayerCharacter::Load3D` | 0x16E2580 | при наличии VRIK заменяет узлы оружия **третьего лица** на `BSFadeNode` | `src/main.cpp:7268`, `7681-7684`, `7269-7325` |
| `hook:vtbl@0x18620F0 ahkpCharacterProxy::updateManifold` | 0x18620F0 | фильтрует попадания прокси игрока по ragdoll-телам: толкание, «проход насквозь» с прозрачностью, отключение LookAt | `src/main.cpp:6962`, `7691-7694`, `6963-7216` |
| `hook:vtbl@0x16D7780 Character::IAnimationGraphManagerHolder::NotifyAnimationGraph` | 0x16D7780 | отмечает время анимаций `NPC_Bump*` (признак, что толчок сыграл) | `src/main.cpp:8116`, `8354-8355`, `8117-8145` |
| `hook:vtbl@0x16E2BF8 PlayerCharacter::NotifyAnimationGraph` | 0x16E2BF8 | пустой, только `_DEBUG` | `src/main.cpp:8148`, `8356-8359` |
| `hook:vtbl@0x16E2618 PlayerCharacter::UpdateAnimation` (слот 0x7D) | 0x16E2618 | после взмаха подменяет `deltaTime` на N кадров — «проматывает» анимацию атаки | `src/main.cpp:8161-8169`, `8361-8362`, `1245` |
| `hook:vtbl@0x16F5148 HitFrameHandler::Handle` | 0x16F5148 | для игрока анимационный кадр удара засчитывается только при активном физическом взмахе | `src/main.cpp:5969-5985`, `8364-8365` |
| `hook:vtbl@0x16F4FC8 AttackWinStartHandler::Handle` | 0x16F4FC8 | для игрока — пропуск | `src/main.cpp:5988-5999`, `8367-8368` |
| `hook:vtbl@0x16F4FE0 AttackWinEndHandler::Handle` | 0x16F4FE0 | для игрока — пропуск | `src/main.cpp:6002-6013`, `8370-8371` |
| `hook:vtbl@0x16F4FF8 AttackStopHandler::Handle` | 0x16F4FF8 | для игрока пропуск, пока идёт физический взмах | `src/main.cpp:6016-6031`, `8373-8374` |
| `hook:vtbl@0x16D7338 Actor::SetPosition` | 0x16D7338 | телепорт актёра → временно исключить из активных (2,5 с + разброс) | `src/main.cpp:6034-6048`, `8376-8379`; ini `:405` |

### 1.4. Байтовые заплаты

| ресурс | адрес | байты | смысл | условие | доказательство |
|---|---|---|---|---|---|
| `patch:0x6E5366 jcc→jmp E9 A6 00 00 00 (VR melee collision enable)` | 0x6E5366 | `E9 A6 00 00 00` | движок больше не включает свою VR-коллизию оружия (тело `VRMeleeData.collisionNode`) | всегда | `src/main.cpp:7469`, `7934-7937` |
| `patch:0x6E5161 NOP×6 (BSGeometry::SetVRMeleeAlphaAndEmissive→SetFadeNodeAlpha)` | 0x6E5161 | `90×6` | движок больше не гасит оружие прозрачностью; PLANCK делает это сам | всегда | `src/main.cpp:7494`, `7577-7580` |
| `patch:0x74D65B NOP×11 (GetUpStart zero pitch/roll)` | 0x74D65B | `90×11` | не обнулять наклон/крен при начале вставания | `dontResetPitchRollWhenGettingUp` | `src/main.cpp:7493`, `7572-7575` |

## 2. Кадр: точки обновления и их порядок

| № | ресурс | где крутится | что PLANCK там делает | доказательство |
|---|---|---|---|---|
| F0 | `frame:SKSEVR WaitGetPoses (RegisterForPoses, prio 11)` | начало кадра, поток OpenVR | скорость обоих контроллеров из поз OpenVR → мир Skyrim, скользящее среднее | `src/main.cpp:8342`, `7978-8054` |
| F1 | `frame:SKSEVR ControllerState (RegisterForControllerState, prio 11)` | опрос контроллеров | ось-джойстик каждой руки (для «силовой атаки вперёд») | `src/main.cpp:8343`, `8056-8090`, `1153-1163` |
| F2 | `frame:HIGGS PlayerCharacterUpdateHook→PreVrikPreHiggs` | до обновления HIGGS и VRIK | локальная позиция wand-узлов → история, угловая скорость; мировая матрица кости руки 1-го лица | `src/main.cpp:8254`, `4033-4050`; HIGGS `src/hooks.cpp:519-524` |
| F3 | `frame:PlayerCharacter::UpdateAnimation` | анимация игрока | промотка анимации после взмаха | `src/main.cpp:8162-8169` |
| F4 | `frame:PlayerCharacter::UpdateWeaponSwing@0x6ABCA4` | обновление игрока | машина состояний взмаха × 2 руки, запуск атаки/силовой/удара щитом | `src/main.cpp:4027-4031`, `1254-1312` |
| F5 | `frame:ProcessHavokHitJobs@0x6497E4` | главный цикл | см. ниже | `src/main.cpp:4340-4822` |
| F6 | `frame:MovementControllerUpdate@0x5E086F → CheckAndHandleMotionOrAnimationDrivenChange@0x5E0885 → ModifyMovementData(vtbl) → MovementPlannerArbiter@0x116D362/0x116D39D` | обновление каждого NPC | толчки, motion-driven схваченного NPC, ограничение движения | `src/main.cpp:5749-5766`, `6441-6776`, `6236-6321`, `6811-6838` |
| F7 | `frame:anim graph update (PreGenerate@0xB1CB55, collectActiveNodes@0xA88B6A, beginTransition@0xA55AC1, CyclicBlend::handleEvent, BSLookAtModifier::modify, NotifyAnimationGraph)` | генерация графа поведения | принудительная генерация, снимки позы до LookAt, правка переходов | `src/main.cpp:5718-5726`, `6844-6957`, `7222-7263`, `8117-8145` |
| F8 | `frame:hkbRagdollDriver::driveToPose@0xB266AB` (→ `@0xA26C05` → `@0xBA3B36`) | шаг физики графа, до `hkpWorld::stepDeltaTime` | управление активным ragdoll | `src/main.cpp:5690-5697`, `4886-5573`, `6190-6199`, `6391-6408`; `src/main.cpp:3474` (комментарий: driveToPose идёт от слушателя физического шага графа) |
| F9 | `frame:HIGGS PrePhysicsStepHook→PrePhysicsStepCallback` | сразу перед `hkpWorld::stepDeltaTime`, **после** всех driveToPose | очередь импульсов, выключение VR-тела оружия движка, «задерживающиеся» тела HIGGS | `src/main.cpp:8253`, `2748-2812` (комментарий `2750`); HIGGS `src/hooks.cpp:706-710` |
| F10 | `frame:hkpWorld step callbacks` | внутри шага Havok | фильтр столкновений (через HIGGS), contactPoint, collisionAdded/Removed, entityAdded, postSimulation; прокси игрока: updateManifold, objectInteraction, processConstraints; linearCast | `src/main.cpp:2625-2746`, `1967-2327`, `2329-2352`, `2483-2504`, `2354-2481`, `6963-7216`, `2551-2617`, `7347-7378`; HIGGS `src/hooks.cpp:699-702` |
| F11 | `frame:hkbRagdollDriver::postPhysics@0xB268DC` (→ `@0xA2921E`, `@0xA374B6`, `@0xA37533`, `@0xB51008`) | после шага | снимки поз, смешивание, возврат гравитации | `src/main.cpp:5700-5705`, `5577-5687`, `6128-6180` |
| F12 | `frame:UpdateRagdollPostPhysics→UpdateFromCharacterControllerAndFootIK@0x703367` | после физики | принудительное обновление ориентации контроллера | `src/main.cpp:6216-6230` |
| F13 | `frame:PreCullActors@0x69F4B9` | перед отрисовкой | запрет отсечения активных | `src/main.cpp:5707-5715` |
| F14 | `frame:SKSE task queue` | очередь задач главного потока | выполнение удара (`DoActorHitTask`, `DoRefrHitTask`), смена слоя, пакеты ИИ, снятие не-ragdoll тел | `src/main.cpp:1579-1741`, `1744-1785`, `3682-3706`, `5769-5800` |

**Порядок F2–F5 из исходника не выводится [вывод]**: PLANCK не фиксирует, где именно вызывается
`ProcessHavokHitJobs` относительно обновления игрока. F0→F1 — по устройству OpenVR; F8→F9→F10→F11 —
по комментариям `src/main.cpp:2750`, `5436`, `5579`, `5602` и хукам HIGGS. F6 до F7 — по порядку адресов
`0x5E086F` < `0x5E0885` внутри одной функции [вывод].

### 2.1. Что делает F5 (`ProcessHavokHitJobsHook`) по шагам

| шаг | действие | строки |
|---|---|---|
| 1 | время кадра, группа коллизий игрока | `src/main.cpp:4365-4370` |
| 2 | при смене мира: сброс объектов, установка своих слушателей Havok, **переписывание матрицы слоёв** Biped/BipedNoCC | `4374-4439` |
| 3 | при смене прокси игрока: свой слушатель прокси, **замена формы контроллера игрока** и радиуса капсулы | `4441-4573` |
| 4 | опрос HIGGS (`UpdateHiggsInfo`), перевод тел рук/оружия HIGGS в `KEYFRAMED_REPORTING` | `4575`, `4261-4313`, `4244-4259` |
| 5 | возврат рук HIGGS после вынужденного броска | `4576`, `3773-3783` |
| 6 | замедление игрока и расход выносливости за удерживаемых NPC | `4579`, `3787-3880` |
| 7 | прозрачность оружия игрока | `4581`, `930-944` |
| 8 | отложенные задачи | `4583`, `333-349` |
| 9 | **перестановка своего контакт-слушателя в конец массива мира** каждый кадр | `4585-4599` |
| 10 | чистка кулдаунов толчка/рывка за ногу | `4601-4619` |
| 11 | выход, если мир сменился < `worldChangedWaitTime` (4 с) назад | `4621-4623`; ini `:65` |
| 12 | цикл по `processManager->actorsHigh`: действие над схваченным, толчок, агрессия, добавление/удаление ragdoll в мир, группы коллизий, самоколлизия | `4637-4809` |
| 13 | сглаженное смещение игрока | `4817-4821` |

## 3. Запись в состояние движка

### 3.1. Коллизии: слои, матрица, биты, контакты

Номера слоёв: Clutter 4, Weapon 5, Projectile 6, Spell 7, Biped 8, Props 10, Trap 14, Ground 17,
CharController 30, DeadBip 32, BipedNoCC 33 (`D:\Skyrim VR Modding\SKSE VR Source\sksevr_2_00_12\src\sksevr\skse64\GameForms.h:562-595`);
слой HIGGS — 56 по умолчанию, дальше читается со слоя руки HIGGS (`src/main.cpp:462`, `4278-4280`).

| ресурс | доступ | что и когда | доказательство |
|---|---|---|---|
| `collision:layer8 Biped bitfield (world filter)` | write | при смене мира: обнуление (`disableBipedCollisionWithWorld=1`), затем ИЛИ с Biped, Clutter, Weapon, Props, Trap, Spell, Projectile, DeadBip по флагам; затем `ReSyncLayerBitfields` — зеркально переписывает **столбец слоя 8 у всех 64 слоёв** | `src/main.cpp:4397-4426`; `src/RE/havok.cpp:232-243`; ini `:523-530` |
| `collision:layer33 BipedNoCC bitfield` | write | ИЛИ с BipedNoCC, DeadBip; ReSync | `src/main.cpp:4428-4434` |
| `collision:layer56 HIGGS bitfield` | write (через API HIGGS) | на PostPostLoad добавляет Biped и BipedNoCC к слою HIGGS | `src/main.cpp:8257-8260` |
| `collision:layer8/33 original bitfields` | read | исходные поля слоёв сразу после `SetFromBGSCollisionLayers` — для решения «не-актёрный Biped» | `src/main.cpp:6204-6211`, `1793-1817` |
| `collision:filter compare callback (via HIGGS)` | own | свой колбэк сравнения фильтров: Biped×Biped (самоколлизия по группам, межактёрная по флагу), подмена слоя Ground→CharController для группы игрока, контроллер игрока × Biped (только активные группы, не удерживаемые, не призванные/спутники), HIGGS × чужой CharController (только «бьющиеся по контроллеру», напр. огоньки) | `src/main.cpp:8252`, `2625-2746`; HIGGS `src/hooks.cpp:699-702`, `src/pluginapi.cpp:208-218` |
| `collision:group sets (active/noPlayerCC/hittableCC/selfCollidable)` | own | группы коллизий актёров, по которым решает колбэк; меняются в F5 | `src/main.cpp:445-448`, `4752-4806`, `3567-3571` |
| `collision:filterInfo bit14 (0x4000) disable on VRMeleeData.collisionNode` | write | каждый шаг: если коллизия VR-тела оружия движка включена — выставить бит 14 и обновить фильтр | `src/main.cpp:2759-2771` |
| `collision:filterInfo layer→32 DeadBip on non-ragdoll biped bodies` | write | тела слоя Biped у персонажа, не входящие в ragdoll (одежда, оружие NPC), при добавлении в мир переводятся в DeadBip | `src/main.cpp:2483-2504`, `1744-1785`; ini `:734` |
| `collision:self-collision refresh (hkpWorld::updateCollisionFilterOnEntity)` | call | при смене самоколлизии — обновить фильтр всех костей ragdoll под write-lock мира | `src/main.cpp:278-313`, `4792-4803` |
| `collision:contact CONTACT_IS_DISABLED` | write | гасит контакт-пойнты: клаттер×контроллер активного NPC, Biped×неподвижные клаттер/оружие/ловушки, не-актёрный Biped, ragdoll×ragdoll по API-игнору, близким актёрам и «на транспорте», рука×рука HIGGS, удар в кулдауне, неударяемый контроллер, удерживаемое/брошенное, удар при опущенном оружии, keyframed-«не удар», игрок в ragdoll/плавает/оглушён | `src/main.cpp:1967-2327`, `1889`, `1897` |
| `collision:layer17 Ground linearCast hits (player group)` | write | вычёркивает попадания по актёрам из `g_dontCollideActors` в коллекторах roomscale-кастов игрока | `src/main.cpp:7327-7378` |
| `collision:player proxy manifold hits` | write | вычёркивает из коллекторов прокси игрока мелкие расы и «проходимых насквозь» | `src/main.cpp:6988-7096` |
| `havok:world contact listener order` | write | свой слушатель принудительно последний в `m_contactListeners` (вызывается первым) — каждый кадр | `src/main.cpp:4585-4599` |
| `havok:world listeners (contact/postSimulation/entity) + collision callback util` | own | ставятся при смене мира под write-lock | `src/main.cpp:4380-4396` |
| `havok:player charProxy listener` | own | `hkpCharacterProxyListener` на прокси игрока | `src/main.cpp:4441-4450` |

### 3.2. Тела, констрейнты, движение Havok

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `havok:HIGGS hand/weapon rigidbody qualityType=KEYFRAMED_REPORTING` | write | **PLANCK меняет тела, которыми владеет HIGGS**, каждый кадр проверяя и при необходимости обновляя фильтр | `src/main.cpp:4244-4259`, `4273-4276` |
| `havok:ragdoll rigidbody motionType=DYNAMIC` | write | при добавлении в мир | `src/main.cpp:3162` |
| `havok:ragdoll rigidbody maxLinear/maxAngularVelocity` | write | при добавлении в мир | `src/main.cpp:3164-3165` |
| `havok:ragdoll rigidbody activate` | write | при добавлении; при ослаблении констрейнтов | `src/main.cpp:3167-3169`, `5176-5182` |
| `havok:ragdoll constraints limitedHinge→ragdoll` | write | замена констрейнтов на ragdoll-констрейнты, перенос в мир | `src/main.cpp:3174-3202` |
| `havok:ragdoll constraint limits/pivots (ease constraints)` | write | каждый driveToPose: временная установка тел в анимационную позу, `hkpEaseConstraintsAction` ослабляет пределы, пивоты в мировом пространстве, постепенный возврат пределов | `src/main.cpp:5024-5185` |
| `havok:ragdoll rigidbody transform (temp)` | write | подмена `motionState.m_transform` на время расчёта ослабления и возврат | `src/main.cpp:5035-5041`, `5123-5127` |
| `havok:ragdoll warp setTransform + zero velocity` | write | «телепорт» всех костей в анимационную позу и `hkbRagdollDriver::reset` | `src/main.cpp:5374-5400` |
| `havok:ragdoll gravityFactor 0/1` | write | 0 до driveToPose, 1 после postPhysics и при смерти | `src/main.cpp:5332-5337`, `5642-5647`, `3646-3679`, `5737-5747` |
| `havok:constraint enabled=false` | write | при `disableConstraints` или расе из списка | `src/main.cpp:5568-5572` |
| `havok:impulse point/linear on actor bodies` | write | импульс удара (точка + 3 волны соседей), рывок; исполняется в F9 | `src/main.cpp:205-254`, `1440-1512`, `2754-2757` |
| `havok:player charController shape (hkCharControllerShape verts)` | write | новая выпуклая форма с радиусом 0,15, подмена в list-shape или фантоме | `src/main.cpp:4457-4538`; ini `:743,754` |
| `havok:player capsule radius/vertices` | write | радиус 0,15, центрирование | `src/main.cpp:4540-4568`; ini `:750-755` |
| `havok:NPC charController fallTime/fallStartHeight` | write | пока тело в руке HIGGS | `src/main.cpp:6054-6060` |
| `havok:NPC charController doOrientationUpdate/calculatePitchTimer` | write | принудительная ориентация | `src/main.cpp:6220-6229` |
| `havok:NPC charController outVelocity` | write | убирает компоненту к игроку | `src/main.cpp:6261-6267` |
| `havok:NPC charController ApplyVelocityForDuration` | call | отталкивает NPC от игрока | `src/main.cpp:7156-7200` |
| `havok:charProxy objectImpulse / surface velocity` | write | импульс игрока по Biped ×0 (в сборке), нулевая скорость поверхностей ragdoll | `src/main.cpp:2567`, `2585-2617`; ini `:447` |

### 3.3. Граф поведения и драйвер ragdoll (`include/RE/havok_behavior.h`)

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `anim:hkbGeneratorOutput TRACK_RIGID_BODY_RAGDOLL_CONTROLS` | write | принудительное включение, усиления hierarchy/velocity/position, snap-контроллер после добавления | `src/main.cpp:4824-4838`, `5217-5271` |
| `anim:hkbGeneratorOutput TRACK_POWERED_RAGDOLL_CONTROLS` | write | принудительное включение, onFraction, maxForce/tau/damping (обычные и «вставание») | `src/main.cpp:4840-4854`, `5225-5240`, `5273-5295` |
| `anim:hkbGeneratorOutput TRACK_WORLD_FROM_MODEL` | write | плавное затухание вычисляемого worldFromModel | `src/main.cpp:4967-4981` |
| `anim:hkbGeneratorOutput TRACK_POSE` | write | нулевой сдвиг корня при движении схваченного, копия позы с foot IK, смешивание Blender, принудительные позы | `src/main.cpp:5010-5013`, `5310-5330`, `5651-5684`; `src/blender.cpp:64-110` |
| `anim:hkbRagdollDriver.shouldReinitializeRagdollController` | write | после варпа | `src/main.cpp:5396-5397`; `include/RE/havok_behavior.h:73` |
| `anim:hkbRagdollDriver.reportingWhenKeyframed` | write (мёртвый код) | `SetBonesKeyframedReporting` нигде не вызывается | `src/main.cpp:4856-4870`; `include/RE/havok_behavior.h:58` |
| `anim:BShkbAnimationGraph.world` | write | ставится, если пуст, и обнуляется при снятии | `src/main.cpp:3473-3477`, `3547-3549`; `include/RE/havok_behavior.h:742` |
| `anim:BShkbAnimationGraph::UpdateData.forceUpdate` | write | для активных | `src/main.cpp:5722`; `include/RE/havok_behavior.h:692` |
| `anim:hkaSkeletonMapper simpleMappings (anim↔ragdoll)` | write | переписывает таблицы отображений пересечением двух направлений | `src/main.cpp:3212-3321`; ini `:611` |
| `anim:hkbNodeInfo.ignoreEvents (BSCyclicBlendTransitionGenerator)` | write | снятие игнора событий | `src/main.cpp:6886-6893` |
| `anim:BSCyclicBlendTransitionGenerator.state` | write | CrossBlend→None перед CyclicFreeze | `src/main.cpp:6914-6924` |
| `anim:hkbBlendingTransitionEffect.selfTransitionMode` | write | RESET→CONTINUE | `src/main.cpp:6946-6953` |
| `anim:BSLookAtModifier.lookAtTarget` | write | временно false и обратно | `src/main.cpp:7243-7262` |
| `anim:BSAnimationGraphManager ragdoll in world` | call | `AddRagdollToWorld`, `SetRagdollConstraintsFromBhkConstraints`, `RemoveRagdollFromWorld`, `DisableOrEnableSyncOnUpdate` (каждый кадр для активных), `RemoveNonRagdollRigidBodiesFromWorld` | `src/main.cpp:3519-3524`, `3596`, `3617`, `4778`, `5789`; адреса `src/RE/offsets.cpp:237-244` |
| `anim:Actor.flags2 bit8 (force anim update)` | write | каждый кадр для активных | `src/main.cpp:4780-4783` |
| `anim:staggerMagnitude, staggerDirection (float vars) + staggerStart event` | write | шатание после толчка, если анимация толчка не сыграла | `src/main.cpp:599-614`, `3928-3937` |
| `anim:IsBlocking (bool var)` | write (мёртвая ветка) | только если `IsPhysicallyBlocked`, а он всегда `false` | `src/main.cpp:5846-5866` |
| `anim:player attackData->event notify` | write | событие силовой атаки/удара щитом в граф игрока | `src/main.cpp:1056`, `1101` |
| `anim:bAllowRotation, IsBashing (Papyrus read spoof)` | hook | подмена значений для Papyrus во время взмаха | `src/main.cpp:5911-5937` |
| `anim:NPC_BumpFromFront/NPC_BumpedFromRight/Back/Left events` | read | факт проигрыша толчка | `src/main.cpp:8117-8134` |
| `anim:moveStart event id / state machine transitions` | read | можно ли начинать движение из текущего состояния | `src/main.cpp:4315-4335`, `6855-6884` |

### 3.4. Узлы

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `node:WEAPON/SHIELD (1st person, или 3rd при VRIK) fade` | write | каждый кадр `SetFadeNodeRecurse` + `SetCurrentFade(alpha)` — оружие становится полупрозрачным (0,25), пока идёт кулдаун удара/игнор коллизии | `src/main.cpp:930-944`, `2463-2480`; `src/utils.cpp:1501-1514`; ini `:54` |
| `node:WEAPON, WeaponSword, WeaponDagger, WeaponAxe, WeaponMace, SHIELD, WeaponBack (3rd person) → BSFadeNode` | write | структурная подмена узлов скелета третьего лица игрока, правка `BSFlattenedBoneTree`, обновление `BOM`; только при VRIK | `src/main.cpp:7269-7325`; ini `:490` |
| `node:animation graph boneNodes entries` | write (только в установленной сборке) | перепривязка указателей костей на новый узел | `mods\PLANCK VR Lifetime and Collision Alpha Fix\Source\src\main.cpp:7365`; `…\DOWNSTREAM_PATCH.md:3-15` |
| `node:HmdNode world/local` | read | конус «агрессивной» руки, угол взмаха, OpenVR→мир | `src/main.cpp:7982-8001`, `1280-1288`, `410-411`; `src/utils.cpp:1477-1494` |
| `node:Left/RightWandNode local pos` | read | история позиций руки в F2 | `src/main.cpp:4039-4044`; `include/utils.h:98` |
| `node:Left/RightHandBone (1st) world` | read | «сырая» рука до HIGGS/VRIK, направление удара кулаком | `src/main.cpp:4047-4048`, `2268-2269`; `src/utils.cpp:1449-1455` |
| `node:Left/RightMeleeWeaponOffsetNode m_oldWorldTransform` | read | направление укола (кадр назад, чтобы не видеть правку двуручного хвата HIGGS) | `src/main.cpp:2255-2257` |
| `node:actor torso/head → core ragdoll bodies` | read | путь от корня до торса/головы по графу констрейнтов | `src/main.cpp:3327-3436` |

### 3.5. Настройки игры и ini

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `setting:fMinSoundVel (0x1E94F78)` | write | временно поднимается, чтобы заглушить звук столкновений ragdoll; возврат в postSimulation | `src/RE/offsets.cpp:27`, `src/main.cpp:2069-2073`, `4991-4994`, `2356-2359`, `8195` |
| `setting:fPhysicsDamage1..3Mass/Damage, fPhysicsDamageSpeedBase/Mult/Min` | read | своя формула физического урона | `src/main.cpp:140-180`, `2059-2060`; `src/RE/offsets.cpp:54-62` |
| `setting:fExplosionKnockStateExplodeDownTime` | read | таймер нокдауна | `src/main.cpp:6065`, `6074` |
| `setting:globalTimeMultiplier, havokWorldScale, deltaTime` | read | везде | `src/RE/offsets.cpp:7-25` |
| `setting:activeragdoll.ini (все ключи)` | own | чтение при загрузке; `SetSettingDouble` из API/Papyrus меняет значения на лету | `src/config.cpp:189`, `147`, `617-624`, `637-642` |
| `setting:iniLogLevel` | own | уровень журнала | `src/main.cpp:8315-8316` |

### 3.6. Значения актёров, урон, бой, поля структур

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `equip:AV Stamina (26) damage` | write | стоимость взмаха, силовой атаки, удара щитом, толчка, рывка, удержания NPC | `src/main.cpp:990-1007`, `3855-3857`, `3882-3917`; `include/utils.h:150` |
| `equip:AV SpeedMult (30) temporary + CarryWeight (32) ±0.1` | write | замедление игрока при удержании NPC | `src/utils.cpp:1100-1110`, `src/main.cpp:3844-3852` |
| `equip:AV regen delay (26)` | write | задержка восстановления после исчерпания | `src/main.cpp:1001-1004`, `3896-3899` |
| `equip:AV Health (24)` | read | «мелкий» актёр, порог ragdoll | `src/main.cpp:824`, `849` |
| `equip:player equipped object (main/offhand)` | read | оружие удара, щит, факел | `src/main.cpp:2240-2241`, `1165-1171`, `1324-1326` |
| `equip:actorState.flags04 attackState bits 28-31` | write | kSwing/kBash/0 вокруг удара | `include/utils.h:163-167`; `src/main.cpp:1186`, `1241`, `1267`, `1328`, `1378`, `1404`, `1414` |
| `equip:player+0x12D7 |= 0x1C` | write | флаги силовой атаки [вывод: назначение по комментарию] | `src/main.cpp:1063`, `1338` |
| `equip:player+0x6BC lastHitPosition, +0x6C8 lastHitVelocity` | write | перед `HitTarget` | `src/main.cpp:1605-1609`, `1699-1703` |
| `equip:VRMeleeData.swingDirection (player+0x710)` | write | направление силовой атаки по угловой скорости | `src/main.cpp:1145-1163`; `include/utils.h:87` |
| `equip:BGSAttackData (UpdateAndGetAttackData)` | call | выбор атаки/силовой | `src/main.cpp:1015-1046`, `1601` |
| `equip:HitData.flags bit30 (PLANCK hit), bit29 (PLANCK physics damage)` | write | «неиспользуемые» биты как протокол | `src/main.cpp:5875-5880`, `1945-1947` |
| `equip:Actor::HitTarget / Actor::GetHit / QueueDamageObjectTask` | call | удар по актёру, физический урон, урон разрушаемым | `src/main.cpp:1369`, `1951`, `1399`, `1958` |
| `equip:middleProcess+0x2B0 knock timer` | write | сброс, пока тело держат | `src/main.cpp:6063-6067` |
| `equip:Actor.unk274 cull state` | write | «не отсекать» | `src/main.cpp:5711-5714` |
| `equip:Actor alpha (vfunc 0xE3/0xE4)` | write/read | полупрозрачность «проходимого насквозь» NPC; тот же слот `GetAlpha`, что портил NPC Spell Variance | `src/main.cpp:7061-7071`, `7125-7131`; `…\DOWNSTREAM_PATCH.md:36-44` |

### 3.7. ИИ, движение, диалоги

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `anim:bump state/direction + Actor::GetBumped` | write | толчок NPC (малый/большой) | `src/main.cpp:546-555`, `5753-5763` |
| `anim:PushActorAway` | call | ragdoll при хвате/рывке/сбое вставания | `src/main.cpp:4079-4087`, `5200-5209` |
| `anim:MovementPlannerDirectControl target speed/direction/angle` | write | ведение схваченного NPC | `src/main.cpp:6482-6484`, `6763-6773` |
| `anim:ActorProcess rotationSpeedZ, a_rotAmt, a_moveAmt` | write | поворот и ограничение движения | `src/main.cpp:6315-6318`, `6253-6258` |
| `form:Assault alarm / StopCombatAlarm` | call | агрессия NPC | `src/main.cpp:3018`, `3047` |
| `form:dialogue topics/topicInfos (ini + API)` | call | реплики при толчке, агрессии, ragdoll | `src/main.cpp:2842-2894`, `4061-4077` |
| `form:keywords ActorTypeAnimal, ActorTypeNPC` | read | классификация | `src/main.cpp:8197-8202` |
| `form:EvaluatePackage` | call | после конца ведения схваченного | `src/main.cpp:3682-3706`, `6465` |

### 3.8. Звук, эффекты, тактильность

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `haptics:PlayRumble (0xC59440)` | call | подтверждение удара (двуручно — обе руки), провал взмаха, толчок | `src/utils.cpp:1112-1125`; `src/main.cpp:1592`, `3964-3970`; `src/RE/offsets.cpp:362` |
| `haptics:VRMeleeData.impactConfirmRumble*` | read | интенсивность и длительность из данных движка | `src/utils.cpp:1115-1123` |
| `form:impact data set / material / particle` | call | звуки и частицы удара по миру | `src/main.cpp:1514-1576` |
| `form:weapon swing sound (engine)` | hook | заглушён для игрока, играет свой звук провала | `src/main.cpp:5940-5965`, `1106-1120` |
| `form:HUD meter flash (26)` | call | нехватка выносливости | `src/main.cpp:1004`, `3870` |

### 3.9. События

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `event:TESHitEvent (produce)` | write | PLANCK сам шлёт `TESHitEvent` при ударе по объектам со скриптами/подвижным/статичным | `src/main.cpp:97-138` |
| `event:TESHitEvent → PlanckHitEvent (extend)` | hook | подмена отправки для своих ударов | `src/main.cpp:5883-5908` |
| `event:MenuOpenCloseEvent` | own (sink) | копия MenuChecker Shizof | `src/main.cpp:8204-8206`; `src/menu_checker.cpp:91-117` |
| `event:TESCellAttachDetachEvent` | own (sink) | снятие активного ragdoll при выгрузке ячейки | `src/main.cpp:8171-8189`, `8208-8215` |
| `event:SKSE PostLoad/PostPostLoad/PostLoadGame/NewGame/DataLoaded` | own | регистрация своего API, подключение HIGGS, сброс | `src/main.cpp:8228-8276` |

## 4. Что PLANCK берёт у HIGGS и VRIK

### 4.1. HIGGS (обязательная зависимость, сборка ≥ 1060000)

| ресурс | доступ | когда | доказательство |
|---|---|---|---|
| `api:HIGGS.GetBuildNumber` | call | PostPostLoad, иначе фатальная ошибка | `src/main.cpp:8247-8250`, `8265-8266` |
| `api:HIGGS.AddCollisionFilterComparisonCallback` | call | PostPostLoad | `src/main.cpp:8252` |
| `api:HIGGS.AddPrePhysicsStepCallback` | call | PostPostLoad | `src/main.cpp:8253` |
| `api:HIGGS.AddPreVrikPreHiggsCallback` | call | PostPostLoad | `src/main.cpp:8254` |
| `api:HIGGS.AddGrabbedCallback` | call | PostPostLoad; читает `GetGrabTransform` в момент хвата | `src/main.cpp:8255`, `4055-4058` |
| `api:HIGGS.Get/SetHiggsLayerBitfield` | call | PostPostLoad: +Biped, +BipedNoCC | `src/main.cpp:8257-8260` |
| `api:HIGGS.ForceWeaponCollisionEnabled(isLeft)` | call | PostPostLoad, обе руки; у HIGGS это односторонняя защёлка без отмены | `src/main.cpp:8262-8263`; HIGGS `src/pluginapi.cpp:351-354` |
| `api:HIGGS.GetHandRigidBody / GetWeaponRigidBody(isLeft)` | call | каждый кадр F5 | `src/main.cpp:4263-4271` |
| `api:HIGGS.GetGrabbedRigidBody / GetGrabbedObject(isLeft)` | call | каждый кадр F5 | `src/main.cpp:4285-4292` |
| `api:HIGGS.GetGrabTransform(isLeft)` | call | каждый кадр F5 | `src/main.cpp:4303-4304` |
| `api:HIGGS.IsTwoHanding` | call | на каждом контакте-ударе | `src/main.cpp:2245` |
| `api:HIGGS.DisableHand / EnableHand(isLeft)` | call | выбить объект из руки при исчерпании выносливости и вернуть | `src/main.cpp:3764-3783` |
| `havok:HIGGS hand/weapon rigidbody` | write | см. §3.2: `KEYFRAMED_REPORTING` | `src/main.cpp:4244-4276` |

Принадлежность руки. PLANCK определяет руку тела **физически** — по указателю тела HIGGS
(`IsLeftRigidBody`, `src/main.cpp:478-483`), а «вторую руку» для экипировки выводит сам:
`isOffhand = leftHandedMode ? !isLeft : isLeft` (`src/main.cpp:2239`, `1141`). В `PlanckHitData.isLeft`
уходит физическая рука (`src/main.cpp:1364`; `include/planckinterface001.h:21-22`).

### 4.2. VRIK (не зависимость; API не используется)

| ресурс | доступ | что | доказательство |
|---|---|---|---|
| `api:VRIK presence (GetModuleHandle "vrik")` | read | единственная связь: переключает узел оружия на третье лицо и включает подмену узлов 3-го лица | `src/main.cpp:8217`, `934`, `7275-7276` |
| `api:IVrikInterface001` | — | не запрашивается ни разу | `grep -rniE "vrik" src include` — только строки выше |
| `frame:VRIK IK timing` | read (через HIGGS) | порядок «до VRIK» PLANCK получает от HIGGS (`AddPreVrikPreHiggsCallback`), у VRIK такого крючка в публичном API нет | `src/main.cpp:8254`; `local\vrik-re\api\vrikinterface001.h:15-66` |

## 5. API PLANCK для других модов

| поверхность | имя | доказательство | пробел |
|---|---|---|---|
| mod-event | SKSE-сообщение `kMessage_GetInterface = 0x92F38745` → `GetApi(1)` | `src/pluginapi.cpp:10-33` | одна ревизия |
| cpp-interface | `GetBuildNumber` | `include/planckinterface001.h:41` | — |
| cpp-interface | `Add/RemoveIgnoredActor` | `include/planckinterface001.h:47-50` | нет запроса «активен ли актёр», нет событий добавления/снятия ragdoll |
| cpp-interface | `Add/RemoveAggressionIgnoredActor`, `SetAggressionLow/HighTopic` | `include/planckinterface001.h:52-61` | — |
| cpp-interface | `Add/RemoveRagdollCollisionIgnoredActor` | `include/planckinterface001.h:63-65` | проверка идёт в физическом потоке через мьютекс (`src/pluginapi.cpp:109-112`, `src/main.cpp:2082`) |
| cpp-interface | `GetLastHitData` | `include/planckinterface001.h:67-68`, `src/pluginapi.cpp:114-117` | «последний удар» — глобальная ячейка без привязки к руке/цели/кадру |
| cpp-interface | `GetCurrentHitEvent` | `include/planckinterface001.h:70-71` | действительно только внутри отправки |
| cpp-interface | `GetSettingDouble/SetSettingDouble` | `include/planckinterface001.h:73-76` | комментарий говорит «higgs's ini settings» — ошибка копирования |
| cpp-interface | `Deprecated1/2` | `include/planckinterface001.h:43-45` | — |
| mod-event | `PlanckHitEvent : TESHitEvent` + `IsPlanckHit` (магия `0x59914000` во флагах) | `include/planckinterface001.h:25-35`, `src/main.cpp:5890-5897` | нет отдельных событий для толчка, рывка, хвата NPC, ragdoll-on-grab, физического урона |
| papyrus | `PLANCK.GetSetting/SetSetting`, `Add/RemoveIgnoredActor`, `Add/RemoveAggressionIgnoredActor`, `SetAggressionLow/HighTopic`, `Add/RemoveRagdollCollisionIgnoredActor`, `GetLastHitNodeName` | `src/papyrusapi.cpp:52-68` | нет событий Papyrus вообще; при ошибке `GetSetting` возвращает `-2.71828` (`src/papyrusapi.cpp:9`) |
| ini | `Data\SKSE\Plugins\activeragdoll.ini` | `src/config.cpp:617-624` | — |
| other | протокол битов `HitData.flags` 29/30 | `src/main.cpp:1946`, `5877` | не документирован, может столкнуться с чужими модами, использующими те же «свободные» биты |

## 6. Пересечения с HIGGS/VRIK — сырьё для синергии

| что | PLANCK | HIGGS / VRIK | вид |
|---|---|---|---|
| Один и тот же call-site `0x3AFD84` (`bhkLinearCaster::linearCast`) и одна задача — чистить коллекторы кастов игрока | `src/main.cpp:7345-7378` | HIGGS `src/hooks.cpp:820-844`, `1487` | дублирование механики, цепочка хуков |
| Своя детекция скорости контроллеров из поз OpenVR | `src/main.cpp:7978-8054` | HIGGS тоже регистрирует `RegisterForPoses/ControllerState` (HIGGS `src/main.cpp:1167-1168`) | дублирование |
| Копия MenuChecker | `src/menu_checker.cpp` | HIGGS `src/menu_checker.cpp:109` | дублирование |
| Детекция VRIK через `GetModuleHandle` | `src/main.cpp:8217` | HIGGS `src/main.cpp:951` | дублирование |
| Тела рук/оружия: владелец HIGGS, PLANCK переписывает `qualityType` | `src/main.cpp:4244-4276` | HIGGS создаёт тела | спор за ресурс |
| Слой HIGGS: PLANCK дописывает биты Biped/BipedNoCC через API | `src/main.cpp:8257-8260` | HIGGS владеет слоем | согласованное, но однонаправленное |
| Матрица слоёв Biped переписывается целиком (столбец у всех слоёв) | `src/main.cpp:4397-4434`, `src/RE/havok.cpp:232-243` | любой мод со своим слоем | риск молча перетереть чужие биты |
| Порядок контакт-слушателей: PLANCK каждый кадр ставит себя последним | `src/main.cpp:4585-4599` | HIGGS добавляет свой (HIGGS `src/main.cpp:594`) | спор за порядок |
| VR-тело оружия движка (`VRMeleeData.collisionNode`) гасится заплатой + битом 14 | `src/main.cpp:7934-7937`, `2759-2771` | HIGGS держит свои тела оружия | распределение: движок отключён, HIGGS — носитель, PLANCK — судья удара |
| Узлы оружия третьего лица заменяются на `BSFadeNode` «потому что VRIK делает 3-е лицо главным» | `src/main.cpp:7273-7321` | VRIK владеет скелетом 3-го лица; в API нет ни узла оружия, ни уведомления | знание о VRIK зашито в PLANCK |
| «Экипировано» и «может бить» | экипировку читает у движка (`src/main.cpp:2240`), «может бить» — по контакту тела HIGGS | HIGGS `IsWeaponCollisionDisabled` не опрашивается | разные источники истины |
| Физический блок игрока | заглушка `IsPhysicallyBlocked` → `false` | контакт оружия HIGGS с оружием NPC мог бы стать источником | незаконченная механика |

## 7. Стоимость по кадру

| где | что | оценка |
|---|---|---|
| `src/main.cpp:4637-4809` (F5) | цикл по `actorsHigh`: на актёра до трёх захватов `updateLock` графа (`IsAddedToWorld`, `IsAddableToWorld`, `DisableOrEnableSyncOnUpdate` каждый кадр для активных — `3083-3151`, `3605-3619`), мьютекс толчка, `TryUpdateNPCState` | O(N актёров) × блокировки |
| `src/main.cpp:2906-2961` | агрессия каждого NPC каждый кадр: ранг отношений, `IsTeammate`, `IsCalmed` (обход всех активных эффектов, `src/utils.cpp:1441-1447`), `IsHostileToActor`, мьютекс списка игнора | заметно при толпе |
| `src/main.cpp:5024-5185` (F8) | на каждый активный ragdoll: расчёт позы, сохранение/возврат трансформ, пересборка `unordered_map` констрейнтов, **новый `hkpEaseConstraintsAction` каждый кадр** (выделение + ctor + ослабление) | выделения памяти в горячем пути |
| `src/main.cpp:5029-5030`, `5350-5363` | `MapHighResPoseLocalToLowResPoseWorld` до трёх раз за driveToPose | дублируемый расчёт |
| `src/main.cpp:5596`, `5621`, `7236`, `5355`, `5369` | копирование поз в `std::vector` (anim, ragdoll, preLookAt, lowRes×2) каждый кадр на актёра | ~5 копий × кости × 48 байт |
| `src/main.cpp:2625-2746` | колбэк фильтра, «сотни раз за кадр» по словам HIGGS; поиск в четырёх `unordered_set` | горячий путь |
| `src/main.cpp:1967-2327` | каждый контакт-пойнт: цепочка проверок, повторные `GetRefFromCollidable`, `DYNAMIC_CAST`, два мьютекса API для ragdoll×ragdoll | горячий путь в потоке физики |
| `src/main.cpp:2354-2481` | `postSimulation`: `std::map` активных пар, пересборка наборов, три прохода по кулдаунам | O(пар) |
| `src/main.cpp:930-944` | прозрачность оружия каждый кадр: `GetObjectByName("WEAPON"/"SHIELD")` по дереву + рекурсивная установка fade | поиск по имени каждый кадр |
| `src/main.cpp:4585-4599` | проверка и перестановка слушателя под write-lock | дёшево, но пишет общий массив мира |
| `src/main.cpp:6963-7216` | updateManifold: `ForEachRagdollDriver` (захват `updateLock`) на каждое попадание по Biped | O(попаданий) |
| `src/main.cpp:1892`, `1907`, `1579-1741` | удар исполняется задачей SKSE — на следующем проходе очереди | задержка до кадра |
| `src/menu_checker.cpp:109-117` | `isGameStopped` — ~20 поисков по `std::map<std::string>` с созданием строк, каждый кадр | мелочь |

## 8. Мёртвый код и мелочи

| что | доказательство |
|---|---|
| `SetBonesKeyframedReporting` не вызывается | `src/main.cpp:4856-4870` |
| `IsPhysicallyBlocked` всегда `false` — ветка `IsBlocking` мертва | `src/main.cpp:5846-5866` |
| `Actor_GetHit_DispatchHitEventFromHitData_HookLoc` объявлен, не используется | `src/main.cpp:7486` |
| Объявлены и не используются `g_bAlwaysDriveRagdoll`, `g_fMeleeWeaponHavokScale`, `g_fMeleeLinearVelocityThreshold`, `g_fShieldLinearVelocityThreshold`, `g_fMagicHand*`, `g_fQuadrupedPitchMult`, `g_iShadowUpdateFrameDelay`, `fMaxTime*`, дубль `g_minSoundVel` на тот же адрес, что `g_fMinSoundVel` | `src/RE/offsets.cpp:20-80` (grep по src/include вне offsets — 0 вхождений) |

## 9. Открытые вопросы

- **[вывод]** Колбэк фильтра и `contactPointCallback` читают наборы групп (`g_activeBipedGroups` и др.),
  которые F5 меняет без блокировки. Если шаг Havok многопоточен, это гонка. Проверить: в каком потоке
  зовётся `bhkCollisionFilter::CompareFilterInfo` в Skyrim VR.
- **[вывод]** `ahkpCharacterProxy::updateManifold` перехвачен через vtable класса, а в теле хука нет
  проверки, что это прокси игрока (`src/main.cpp:6963-7216`). Если прокси есть и у NPC, глобальные
  `g_prevCollidingActorHandles` перетираются последним вызовом. Проверить: какие актёры используют
  `bhkCharProxyController`.
- Точный порядок F2–F5 внутри кадра исходник не даёт — нужен разбор вызывающих функций по адресам.
