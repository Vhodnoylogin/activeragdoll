# PLANCK: механики, API, связь с HIGGS, горячие точки

Ветка исследования: `research/trinity-synergy` (клон `adamhynek/activeragdoll`, HEAD `f06fc95`, версия
`0.8.1.0` — `include/version.h`). Пути ниже даны от корня репозитория `D:\Skyrim VR Modding\PLANCK`;
пути вида `mods/…` — от `D:\Skyrim VR Modding\MO2\ModOrganizer\Skyrim VR\mods`. Утверждение без ссылки
не делается; вывод, не прочитанный прямо в коде, помечен словом **«вывод»**.

Что стоит в сборке: `PLANCK - Physical Animation and Character Kinetics` 0.8.1 (Nexus 66025) и поверх
него DLL из `PLANCK VR Lifetime and Collision Alpha Fix` 1.3.0 (Nexus 188233, форк Treatid2) —
`mods/PLANCK VR Lifetime and Collision Alpha Fix/README.md:1-4`. Клон уже содержит правку из этого форка
про HIGGS (`SetHiggsBodyReportingQuality`, коммиты `b117b99`, `ce7d269`, слиты в `f06fc95`).

## 0. Главное в пяти пунктах

1. **PLANCK — не только «рэгдолл».** Он целиком заменяет у игрока ближний бой VR: своё определение
   замаха (`src/main.cpp:1254-1316`), свой силовой удар и удар щитом (`src/main.cpp:1010-1105`), свою
   регистрацию попаданий по контактам Havok (`src/main.cpp:1967-2327`), свой урон от брошенных предметов
   (`src/main.cpp:1912-1965`), своё столкновение игрока с NPC (`src/main.cpp:2548-2746`, `6963-7218`),
   систему агрессии NPC с диалогами (`src/main.cpp:2819-3058`) и замедление игрока при переноске тела
   (`src/main.cpp:3711-3880`).
2. **От HIGGS он зависит жёстко** (без HIGGS завершает игру — `src/main.cpp:8264-8267`) и
   использует его как шину: фильтр столкновений, точку перед шагом физики, точку «до VRIK и HIGGS»,
   тела рук и оружия. При этом он **пишет в ресурсы HIGGS**: расширяет битовую маску слоя HIGGS
   (`src/main.cpp:8257-8260`), навсегда включает столкновение оружия (`src/main.cpp:8262-8263`), меняет
   тип качества тел рук и оружия HIGGS (`src/main.cpp:4244-4276`).
3. **С VRIK он не разговаривает вообще**: только проверяет, загружена ли `vrik.dll`
   (`src/main.cpp:8217`), и по этому признаку подменяет узлы `WEAPON`/`SHIELD` третьего лица на
   `BSFadeNode` (`src/main.cpp:7269-7322`). Именно эта подмена дала висячий указатель в графе анимации,
   который чинит патч 1.3.0 (`mods/PLANCK VR Lifetime and Collision Alpha Fix/README.md:8-22`).
4. **API беден для потребителя.** Событие попадания — это `TESHitEvent` с «магией» в поле `flags`
   (`include/planckinterface001.h:25-35`), в нём нет вида удара (колющий, силовой, щит, двуручный),
   тела-ударника, приложенного импульса; вето и изменение попадания невозможны; о толчке, рывке,
   опрокидывании, агрессии, включении активного рэгдолла не сообщается ничем; в Papyrus событий нет
   вовсе (`include/papyrusapi.h:16-63` объявлены, но не используются).
5. **Дублирование с HIGGS:** скорость контроллеров снимается дважды одним и тем же кодом из OpenVR
   (`src/main.cpp:7978-8052` против HIGGS `src/main.cpp:168-188`), «отпустил предмет» PLANCK
   определяет опросом каждый кадр вместо `AddDroppedCallback` (`src/main.cpp:4306-4311`), узел
   схваченной кости ищет сам (`src/main.cpp:645-660`) вместо `GetGrabbedNodeName`
   (HIGGS `include/higgsinterface001.h:130`), отдачу в контроллер даёт через игровой `PlayRumble`
   (`src/RE/offsets.cpp:362`), а HIGGS — через свой `HapticsManager` поверх OpenVR
   (HIGGS `src/haptics.cpp:8-12`).

---

## 1. Точки исполнения (кадр) и перехваты

### 1.1. Где идёт покадровая логика

| Точка | Где установлена | Что в ней делает PLANCK |
|---|---|---|
| `frame:ProcessHavokHitJobs` (главный поток, раз в кадр) | вызов по `0x6497E4`, `src/main.cpp:7459`, `7525-7526` | `ProcessHavokHitJobsHook` `src/main.cpp:4340-4822`: смена мира Havok и перенастройка слоёв, форма капсулы игрока, опрос HIGGS, выносливость, прозрачность оружия, отложенные задачи, цикл по всем `actorsHigh` |
| `frame:HIGGS PreVrikPreHiggs` | `AddPreVrikPreHiggsCallback`, `src/main.cpp:8254` | `PreVrikPreHiggsCallback` `src/main.cpp:4033-4050`: история позиций узла-палочки (wand) в комнатном пространстве, «сырые» мировые трансформы рук до VRIK |
| `frame:HIGGS PrePhysicsStep` (перед `hkpWorld::stepDeltaTime`) | `AddPrePhysicsStepCallback`, `src/main.cpp:8253` | `PrePhysicsStepCallback` `src/main.cpp:2748-2816`: импульсы попаданий из очереди, выключение штатного тела ближнего боя, «задерживающиеся» брошенные тела |
| `frame:Havok contact/post-simulation` | `hkpWorld_addContactListener` и др., `src/main.cpp:4384-4395` | `PhysicsListener` `src/main.cpp:1819-2511`: попадания, урон от предметов, учёт касаний, остывание попаданий |
| `frame:hkbRagdollDriver driveToPose / postPhysics` (на каждого активного NPC) | `0xB266AB`, `0xB268DC` — `src/main.cpp:7463-7465` | `PreDriveToPoseHook` `src/main.cpp:4886-5432`, `PostDriveToPoseHook` `5434-5575`, `PostPostPhysicsHook` `5600-5688` |
| `frame:OpenVR WaitGetPoses` | `RegisterForPoses(…, 11, WaitPosesCB)` `src/main.cpp:8342` | `WaitPosesCB` `src/main.cpp:7978-8054`: скорость контроллеров |
| `frame:OpenVR ControllerState` | `RegisterForControllerState` `src/main.cpp:8343` | `ControllerStateCB` `src/main.cpp:8056-8090`: оси стиков |
| `frame:PlayerCharacter::UpdateWeaponSwing` | вызов по `0x6ABCA4` без оригинала, `src/main.cpp:7461`, `7530` | `PlayerCharacter_UpdateWeaponSwing_Hook` `src/main.cpp:4027-4031` — **заменяет** штатное VR-определение замаха |

### 1.2. Перехваты и заплатки кода игры

Все — в `PerformHooks` `src/main.cpp:7522-7935` и `SKSEPlugin_Load` `src/main.cpp:8304-8391`.

| Ресурс | Адрес | Назначение | Условие |
|---|---|---|---|
| hook:PlayerCharacter::UpdateWeaponSwing call@0x6ABCA4 | `src/main.cpp:7461` | своё определение замаха, штатное не вызывается | всегда |
| hook:ProcessHavokHitJobs call@0x6497E4 | `src/main.cpp:7459` | главный кадр PLANCK | всегда |
| hook:BShkbAnimationGraph::PreGenerate call@0xB1CB55 | `src/main.cpp:7473`, `5718-5727` | принудительная генерация графа у активных | `forceGenerateForActiveRagdolls` `src/main.cpp:7533` |
| hook:hkbRagdollDriver::driveToPose call@0xB266AB | `src/main.cpp:7465`, `5690-5698` | привод рэгдолла к позе | всегда |
| hook:hkbRagdollDriver::postPhysics call@0xB268DC | `src/main.cpp:7463`, `5700-5705` | смешивание поз | всегда |
| hook:hkaRagdollRigidBodyController::driveToPose call@0xA26C05 | `src/main.cpp:7467`, `6190-6199` | контроллер жёстких тел | всегда |
| hook:Actor::TakePhysicsDamage call@0x61F6E7 | `src/main.cpp:7475`, `5729-5735` | гасит штатный урон от физики у активных | всегда |
| hook:Actor::KillEndHavokHit call@0x60C808 | `src/main.cpp:7479`, `5737-5747` | возврат гравитации при смерти | всегда |
| hook:Character::HitTarget→HitData::populate call@0x631CA7 | `src/main.cpp:7485`, `5852-5881` | метка «попадание PLANCK» (бит 30) | всегда |
| hook:DispatchHitEvent branch@0x636742 | `src/main.cpp:7487`, `5883-5909` | подмена `TESHitEvent` на `PlanckHitEvent` | всегда |
| hook:Papyrus GetAnimationVariableBool call6@0x9CE8D0 | `src/main.cpp:7489`, `5911-5937` | подмена `bAllowRotation`, `IsBashing` у игрока | всегда (ветви по ini) |
| hook:WeaponRight/LeftSwingHandler::Handle branch6@0x74B340/0x74B3D0 | `src/RE/offsets.cpp:398-399`, `src/main.cpp:7722-7810` | глушит штатный звук замаха игрока | всегда |
| hook:HitFrameHandler::Handle vtbl@0x16F5148 | `src/main.cpp:5969-5985` | анимационные «кадры удара» игрока — только при активном замахе | всегда |
| hook:AttackWinStart/End/Stop Handler vtbl@0x16F4FC8/0x16F4FE0/0x16F4FF8 | `src/main.cpp:5988-6031` | не даёт графу сбросить состояние атаки | всегда |
| hook:Actor::SetPosition vtbl@0x16D7338 | `src/main.cpp:6034-6048` | временно исключить телепортированного NPC | всегда |
| hook:Actor::IsRagdollMovingSlowEnoughToGetUp call@0x687164 | `src/main.cpp:7491`, `6051-6082` | не вставать, пока держат | всегда |
| patch:0x74D65B nop×11 (GetUpStart обнуляет pitch/roll) | `src/main.cpp:7493`, `7572-7575` | не сбрасывать наклон при подъёме | `dontResetPitchRollWhenGettingUp` |
| patch:0x6E5161 nop×6 (BSGeometry SetVRMeleeAlphaAndEmissive → SetFadeNodeAlpha) | `src/main.cpp:7494`, `7577-7580` | отключает штатное затухание оружия VR | всегда |
| patch:0x6E5366 `E9 A6 00 00 00` (условный переход → безусловный) | `src/main.cpp:7469`, `7931-7934` | штатное тело ближнего боя VR не включается | всегда |
| hook:GetUpEnd ×3 call@0x68727D/0x6872D0/0x74D816 | `src/main.cpp:7496-7498`, `7582-7591` | не убирать рэгдолл после подъёма | `dontRemoveRagdollWhenDoneGettingUp` |
| hook:hkaPoseMatchingUtility::computeReferenceFrame call@0xA2921E | `src/main.cpp:7500`, `6128-6147` | опорный кадр позы | всегда |
| hook:hkpMotion::approxTransformAt call@0xB51008 | `src/main.cpp:7502`, `6149-6165` | трансформ кости | всегда |
| hook:hkaSkeletonMapper::mapPose ×3 call@0xA374B6/0xA37533/0xA28005 | `src/main.cpp:7504-7508`, `6167-6188` | отображение поз рэгдолл↔анимация | всегда |
| hook:bhkCollisionFilter::SetFromBGSCollisionLayers call@0x5BF24F | `src/main.cpp:6203-6211` | запомнить исходные маски слоёв Biped/BipedNoCC | всегда |
| hook:Actor::UpdateFromCharacterControllerAndFootIK call@0x703367 | `src/main.cpp:6215-6231` | принудительное обновление наклона | всегда (ветвь по ini) |
| hook:Character::ModifyMovementData vtbl@0x16D76C0 | `src/main.cpp:6235-6323` | движение схваченного NPC, запрет наступать на игрока | всегда |
| hook:Character::InitLoadGame vtbl@0x16D6E60 | `src/main.cpp:6413-6423` | снять влияние перед загрузкой | всегда |
| hook:Actor::CheckAndHandleMotionOrAnimationDrivenChange call@0x5E0885 | `src/main.cpp:6440-6776` | motion-driven для схваченных | всегда |
| hook:MovementPlanner CalculateSpeeds/RotSpeeds call@0x116D362/0x116D39D | `src/main.cpp:6810-6838` | параметры движения схваченного | всегда |
| hook:hkbUtils::collectActiveNodesLeafFirst call@0xA88B6A | `src/main.cpp:6843-6909` | поиск состояний, разрешающих moveStart | всегда |
| hook:BSCyclicBlendTransitionGenerator::handleEvent vtbl@0x17C5518 | `src/main.cpp:6913-6924` | CyclicFreeze из CrossBlend | всегда |
| hook:hkbStateMachine::beginTransition call@0xA55AC1 | `src/main.cpp:6928-6958` | само-переходы циклических смесей | всегда |
| hook:hkaKeyFrameHierarchyUtility::CalculateApplyKeyframeData call@0xBA3B36 | `src/main.cpp:6390-6409` | своя версия расчёта ключевых кадров | всегда |
| hook:ahkpCharacterProxy::updateManifold vtbl@0x18620F0 | `src/main.cpp:6962-7217` | столкновение игрока с NPC: проход сквозь, отталкивание | всегда |
| hook:BSLookAtModifier::modify vtbl@0x17C68F0 | `src/main.cpp:7221-7263` | выключить взгляд NPC на игрока при столкновении | всегда |
| hook:PlayerCharacter::Load3D vtbl@0x16E2580 | `src/main.cpp:7268-7324` | подмена узлов оружия 3-го лица на `BSFadeNode` | `convertThirdPersonWeaponToFadeNodes` и VRIK |
| hook:hkpWorld::linearCast в bhkLinearCaster call@0x3AFD84 | `src/main.cpp:7345-7379` | убрать NPC из проверок комнатного перемещения | всегда |
| hook:ActorProcess Exit/EnterFurniture call@0x687FF7/0x688061/0x68E344 | `src/main.cpp:7481-7483`, `5803-5844` | мебель и рэгдолл | всегда |
| hook:Character MovementControllerUpdate branch@0x5E086F | `src/main.cpp:7477`, `5749-5766` | задачи движения | всегда |
| hook:PreCullActors branch@0x69F4B9 | `src/main.cpp:7471`, `7900-7929`, `5707-5716` | не отсекать активных NPC | `disableCullingForActiveRagdolls` |
| hook:Character NotifyAnimationGraph vtbl@0x16D7780 | `src/main.cpp:8116-8144`, `8354-8355` | ловит анимации «толкнули» | всегда |
| hook:PlayerCharacter::UpdateAnimation vtbl@0x16E2618 | `src/main.cpp:8161-8169`, `8361-8362` | пропуск кадров анимации игрока после замаха | всегда |

Итого около 45 точек в коде игры, ни одна не согласуется ни с HIGGS, ни с VRIK иначе как через
HIGGS-обратные вызовы. Объявленный адрес `0x62F3DA` (`src/main.cpp:7486`) нигде не используется.

---

## 2. Механики

| Механика | Где живёт | Как устроено | Замечания для синергии |
|---|---|---|---|
| Определение замаха игрока | `SwingHandler::UpdateWeaponSwing` `src/main.cpp:1254-1316` | средняя скорость контроллера выше `swingLinearVelocityThreshold`, затем пик скорости и направление руки к взгляду → `Swing()` | заменяет штатный код игры (`src/main.cpp:7530`); состояние замаха наружу не отдаётся |
| Силовой удар, удар щитом/оружием, стамина | `TrySwingPowerAttack` `src/main.cpp:1010-1066`, `TryBash` `1069-1104`, `Swing` `1139-1252` | силовой = курок зажат во время замаха (`src/main.cpp:1177`, `1190`); направление — по угловой скорости и стику движения (`src/main.cpp:1147-1161`); `PlayerControls_SendAction` | курок читается через `PlayerControls_IsTriggerHeld*` — тот же ввод, что у HIGGS для хвата (вывод) |
| Регистрация попадания рукой/оружием/предметом | `PhysicsListener::contactPointCallback` `src/main.cpp:1967-2327` | контакт тела HIGGS (рука, оружие, схваченное) с чужим телом; классификация «колющий/кулак/мах» по направлению руки и скорости точки (`src/main.cpp:2251-2281`); порог скорости руки в комнатном пространстве (`src/main.cpp:2285`) | тела HIGGS опознаются сравнением указателей с кешем кадра (`src/main.cpp:478-513`) |
| Урон и эффекты попадания по NPC | `DoActorHitTask` `src/main.cpp:1579-1669`, `HitActor` `1321-1382` | задача SKSE → `Actor_HitTarget` игры (штатный расчёт урона); запись позиции/скорости в `player+0x6BC/+0x6C8` (`src/main.cpp:1605-1609`) | урон считает игра, PLANCK выбирает момент и данные |
| Импульс попадания по рэгдоллу | `CalculateHitImpulse`/`ApplyHitImpulse` `src/main.cpp:1418-1477`; очередь `PointImpulseJob`/`LinearImpulseJob` `205-248`, исполнение `2753-2756` | точечный импульс в тело + затухающий в соседние через 3 «волны» связей | импульс наружу не сообщается |
| Попадание по предметам и разрушаемым | `DoRefrHitTask` `src/main.cpp:1671-1741`, `HitRefr` `1402-1416`, `DispatchHitEvents` `97-138`, `PlayImpactEffects` `1554` | ванильный `TESHitEvent` без расширенных данных; урон разрушаемым через `BSTaskPool_QueueDamageObjectTask` | нет `PlanckHitData` для не-актёров |
| Остывание попаданий и прозрачность оружия | `hitCooldownTargets`, `postSimulationCallback` `src/main.cpp:2354-2481`; `UpdateMeleeAlpha` `930-944` | пока оружие «застряло» в NPC — повторных попаданий нет, оружие полупрозрачно (`playerMeleeCollisionDisabledWeaponAlpha` `mods/PLANCK - …/SKSE/Plugins/activeragdoll.ini:54`) | штатное затухание выключено заплаткой `0x6E5161` |
| Урон от брошенных/падающих предметов | `ApplyPhysicsDamage` `src/main.cpp:1912-1965`, вызов `2055-2062`; штатный урон гасится `5729-5735` | формула игры `GetPhysicsDamage` `140-176`; агрессор = игрок, если тело недавно держал HIGGS (`g_higgsLingeringRigidBodies`, `2058`, `2773-2809`) | признак «урон физикой» — бит 29 `HitData.flags` и подмена `sourceFormID` (`src/main.cpp:1944-1949`, `5901-5905`) — недокументированный контракт |
| Активный рэгдолл (включение/выключение по дистанции) | цикл `src/main.cpp:4637-4806`, `AddRagdollToWorld` `3438-3534`, `RemoveRagdollFromWorld` `3573-3603` | в радиусе `activeRagdollStartDistance` (ini `:14`) рэгдолл добавляется в мир, дальше `EndDistance` (ini `:16`) — убирается; не чаще раза в `minFramesBetweenActorAdds` кадров (ini `:67`) | событий «актёр стал активным» нет |
| Смешивание анимации и рэгдолла | `Blender` `include/blender.h:10-52`, `src/blender.cpp:27-134`; старты `src/main.cpp:3463`, `5244`; состояния `5640-5686` | типы `AnimToRagdoll`, `RagdollToCurrentRagdoll` и др.; кривая `PowerCurve` | — |
| Привод к позе, «стресс», ослабление связей | `PreDriveToPoseHook` `src/main.cpp:4886-5432`, `ModifyConstraints` `3153-3204` | параметры powered/rigidbody-контроллеров из ini (`src/main.cpp:5259-5292`), постепенное ослабление связей у лежащих (`5129-5180`) | стресс кости читают только внутри (`GetStress` `714-734`) |
| Опрокидывание при хвате/рывке/за ногу | `GetDesiredGrabbedActorAction` `src/main.cpp:881-925`, `ShouldRagdollOnGrabOrFootYank` `842-869`, применение `4679-4710`, `RagdollActor` `4079-4088` | маленькие расы и раненые падают сразу; рывок = скорость руки при отпускании выше порога; рывок за ногу — по смещению схваченной кости | `ActorProcess_PushActorAway` `src/main.cpp:4085`; события нет |
| Толчок NPC рукой, «bump», шатание | `UpdateActorShove` `src/main.cpp:3919-3982`, `BumpActor` `546-555`, `StaggerActor` `599-615` | рука коснулась NPC со скоростью выше `shoveSpeedThreshold` → bump, при отсутствии анимации толчка — `staggerStart` | ловля анимаций толчка через перехват `NotifyAnimationGraph` `8117-8144` |
| Агрессия NPC к трогающему игроку | `NPCData` `src/main.cpp:2819-3057` | накопленное время хвата → реплика низкая/высокая → `Actor_SendAssaultAlarm` (`src/main.cpp:3018`) | темы реплик задаются через API (`src/main.cpp:2870`) |
| Замедление и расход стамины при переноске | `UpdateSpeedReductionAndStaminaDrain` `src/main.cpp:3787-3880`, `ModSpeedMult` `src/utils.cpp:1100-1109` | временный модификатор `SpeedMult` игрока + дёргание `CarryWeight`; при нуле стамины — `DisableHand` HIGGS (`src/main.cpp:3764-3782`) | PLANCK выбивает предмет из руки HIGGS через отключение руки |
| Движение схваченного NPC | `ShouldDoGrabbedActorMovement` `src/main.cpp:662-702`, `UpdateGrabbedActorMovementState` `4090-4240`, `Character_ModifyMovementData_Hook` `6236-6323` | NPC идёт туда, куда его тянут, motion-driven | — |
| Столкновение игрока с живыми NPC | `CollisionFilterComparisonCallback` `src/main.cpp:2625-2746`, `PlayerCharacterProxyListener` `2548-2621`, `ahkpCharacterProxy_updateManifold_Hook` `6963-7217`, `bhkLinearCaster…_Hook` `7347-7379` | капсула игрока сталкивается с рэгдоллом, а не с капсулой NPC; проход сквозь при глубоком пересечении с полупрозрачностью NPC (`7063-7066`); отталкивание NPC (`7159-7197`) | |
| Уменьшение капсулы игрока | `src/main.cpp:4457-4568` | переписывает вершины `hkCharControllerShape` и радиус капсулы | ini `resizePlayerCharController`, `resizePlayerCapsule` `:743`, `:750` |
| Сталкивания рэгдоллов между собой и с миром | `src/main.cpp:4399-4433`, `2076-2108`, `2630-2643`, самостолкновение `4784-4804` | маски слоёв Biped/BipedNoCC в фильтре мира; самостолкновение включается только пока NPC трогают | API-исключение `AddRagdollCollisionIgnoredActor` |
| Шаги / комнатное перемещение | `src/main.cpp:2653-2668`, `7327-7379` | каст «шагов» игрока на слое Ground считается как капсула; из него удаляются NPC, сквозь которых игрок проходит | — |
| Физическое блокирование ударов NPC | `IsPhysicallyBlocked` `src/main.cpp:5846-5849` | **заглушка, всегда `false`** | механики нет |
| Столкновение оружия NPC | закомментировано `src/main.cpp:5464-5566` | **не реализовано** | механики нет |
| Подъём после падения | `src/main.cpp:6051-6127`, заплатки `7572-7591`, смешивание `5242-5247` | рэгдолл остаётся в мире после подъёма, наклон не сбрасывается | — |
| Пропуск кадров анимации игрока после замаха | `src/main.cpp:8162-8169`, установка `1245` (`g_numSkipAnimationFrames`) | анимация атаки игрока проматывается | **вывод:** влияет на тело, которое показывает VRIK |

---

## 3. API PLANCK

### 3.1. C++ интерфейс `IPlanckInterface001`

Получение: сообщение SKSE `0x92F38745` к «PLANCK» после `PostPostLoad`
(`include/planckinterface001.h:7-9`, `src/planckinterface001.cpp:13-30`); PLANCK регистрирует приёмник на
`PostLoad` (`src/main.cpp:8237-8240`); ревизия одна — `1` (`src/pluginapi.cpp:19-24`).

| Функция | Объявление | Реализация | Замечания |
|---|---|---|---|
| `GetBuildNumber` | `include/planckinterface001.h:41` | `src/pluginapi.cpp:36-41` | `major*1e6+minor*1e4+patch*100+beta` |
| `Deprecated1/2` | `:44-45` | `src/pluginapi.cpp:43-49` | мёртвые слоты ABI |
| `AddIgnoredActor/RemoveIgnoredActor` | `:49-50` | `:59-67` | множество сырых `Actor*`; проверка `src/main.cpp:3125-3128` |
| `AddAggressionIgnoredActor/Remove…` | `:53-54` | `:69-77` | проверка `src/main.cpp:2912-2913` |
| `SetAggressionLowTopic/HighTopic` | `:58-61` | `:79-97` | `nullptr`-актёр = для всех |
| `AddRagdollCollisionIgnoredActor/Remove…` | `:64-65` | `:99-107` | проверка в каждом контакте `src/main.cpp:2082` |
| `GetLastHitData` | `:68` | `:114-117` | копия глобальной структуры, перезаписывается следующим ударом |
| `GetCurrentHitEvent` | `:71` | `:119-121` | валидно только внутри рассылки |
| `GetSettingDouble/SetSettingDouble` | `:75-76` | `:51-57`, `src/config.cpp:147-187` | запись в `Config::options` без синхронизации |

Событие: `PlanckHitEvent : TESHitEvent { void *hitData; PlanckHitData extendedHitData; }`,
опознаётся по старшим 24 битам `flags == 0x59914000` (`include/planckinterface001.h:11-35`); рассылается
вместо штатного события (`src/main.cpp:5883-5899`). `PlanckHitData` = позиция, скорость, узел, имя узла,
`isLeft` (`include/planckinterface001.h:11-23`).

### 3.2. Papyrus `PLANCK`

`mods/PLANCK - Physical Animation and Character Kinetics/Source/Scripts/planck.psc:9-35`,
регистрация `src/papyrusapi.cpp:52-71`: `GetSetting` (нет значения → `-2.71828`), `SetSetting`,
`Add/RemoveIgnoredActor`, `Add/RemoveAggressionIgnoredActor`, `SetAggressionLow/HighTopic`,
`Add/RemoveRagdollCollisionIgnoredActor`, `GetLastHitNodeName`. Событий нет:
`EventFunctor0/2` объявлены в `include/papyrusapi.h:16-63`, но нигде не вызываются.

### 3.3. ini

`Data\SKSE\Plugins\activeragdoll.ini`, секция `Settings` (`src/config.cpp:624`, `22-60`), в сборке
310 ключей (`mods/PLANCK - …/SKSE/Plugins/activeragdoll.ini`). Все числовые ключи доступны через
`Get/SetSettingDouble` (реестр `src/config.cpp:95-113`), но действуют по-разному: часть читается только
при старте или смене мира (например, маски слоёв `src/main.cpp:4399-4433`, заплатки `7533-7591`).
Нет признака «ключ действует на лету», нет уведомления об изменении.

### 3.4. Чего не хватает потребителю

| Разрыв | Доказательство | Последствие |
|---|---|---|
| Нет вида удара в событии: колющий/кулак/мах, силовой, удар щитом, двуручный хват | признаки есть внутри: `isStab` `src/main.cpp:2251-2281`, `isPowerAttack/isBash` `1597-1598`, `isTwoHanding` `2245`; в `PlanckHitData` их нет `include/planckinterface001.h:11-23` | моду «разные эффекты для укола» приходится повторять классификацию |
| Нет тела-ударника (оружие HIGGS, рука, схваченный предмет) и тела-цели | `hittingRigidBody/hitRigidBody` в `DoHit` `src/main.cpp:1878-1910` в событие не попадают | нельзя отличить удар мечом от удара схваченным ведром |
| Нет приложенного импульса и признака смертельности | `impulseMult`, `isFatal` `src/main.cpp:1611-1634` | моды гора/отдачи считают заново |
| Нельзя запретить или изменить попадание | событие рассылается после `HitData::populate` и `Actor_HitTarget` (`src/main.cpp:1367-1369`, `5852-5909`); колбэка «до» нет | фреймворки брони, парирования, неуязвимости не встроятся без своего перехвата |
| Попадание по предметам и урон физикой без расширенных данных | `DispatchHitEvents` шлёт ванильный `TESHitEvent` `src/main.cpp:124-125`; физика — бит 29 и подмена `sourceFormID` `5901-5905` | контракт бита 29 нигде не объявлен |
| `GetLastHitData` глобальна и затирается | `src/pluginapi.cpp:114-117`, запись `src/main.cpp:1356-1365` | Papyrus `GetLastHitNodeName` в `OnHit` может вернуть узел следующего удара (**вывод**: Papyrus-события обрабатываются с задержкой) |
| Нет событий толчка, рывка, опрокидывания, шатания, агрессии, включения рэгдолла, подъёма | механики `src/main.cpp:3919-3982`, `4679-4710`, `3018`, `4744-4749` — наружу ничего | моды реакции NPC дублируют логику |
| Нет запросов состояния по руке | внутри: `handCollidedRefs` `src/main.cpp:1840`, `SwingHandler::IsSwingActive/IsPowerAttackActive` `970-983`, `g_controllerData` `443` | «рука сейчас касается NPC», «идёт силовой замах левой» недоступны |
| Нет запросов по актёру | `IsActiveActor` `src/main.cpp:271-275`, `KnockState` `4932`, `IsDoingGrabbedActorMovement` `704-708` | нельзя спросить «управляет ли PLANCK этим телом» |
| Нет запроса о владении слоями и группами | глобальные множества групп `src/main.cpp:445-448`, маски слоёв `4399-4433` | другой физический мод не знает, какие маски изменены и кем |
| Множества исключений по сырому `Actor*`, не сохраняются и не чистятся при загрузке | `include/pluginapi.h:49-60`; `ResetObjects` их не трогает `src/main.cpp:3984-4025` | потребитель обязан перерегистрировать после каждой загрузки; **вывод:** после выгрузки актёра указатель может достаться другому |
| Версионирование — одна ревизия, мёртвые слоты, отправка сообщения с размером указателя | `src/pluginapi.cpp:19-24`, `include/planckinterface001.h:44-45`, `src/planckinterface001.cpp:22` | расширение возможно только новой ревизией целиком |
| Магическое число в `flags` чужого события | `include/planckinterface001.h:34-35`, `src/main.cpp:5893-5894` | **вывод:** второй мод с той же уловкой сломает опознание |
| Настройки меняются без синхронизации | `src/config.cpp:147-166`; те же поля читает `contactPointCallback` `src/main.cpp:2285` | **вывод:** гонка, если физика идёт в другом потоке |
| В Papyrus нет событий и данных руки | `planck.psc:9-35` | Papyrus-моды ограничены `OnHit` + имя узла |

---

## 4. Как PLANCK использует HIGGS

Заголовок-копия `include/higgsinterface001.h`, получение `src/higgsinterface001.cpp:13-30`, на
`PostPostLoad` (`src/main.cpp:8241-8267`), минимальная сборка HIGGS `1060000` (`src/main.cpp:8247-8250`).
Копия отстаёт от HIGGS: там в конце есть `GetGrabbedNodeName` (HIGGS `include/higgsinterface001.h:130`).

| Функция HIGGS | Где вызывается | Когда | Зачем |
|---|---|---|---|
| `AddCollisionFilterComparisonCallback` | `src/main.cpp:8252` → `2625-2746` | каждое сравнение фильтра | все решения PLANCK о столкновении капсул и бипедов |
| `AddPrePhysicsStepCallback` | `:8253` → `2748-2816` | перед шагом физики | импульсы, выключение штатного тела ближнего боя |
| `AddPreVrikPreHiggsCallback` | `:8254` → `4033-4050` | до VRIK и HIGGS | позиция палочки и рук до IK |
| `AddGrabbedCallback` | `:8255` → `4055-4058` | при хвате | начальный `GrabTransform` |
| `Get/SetHiggsLayerBitfield` | `:8257-8260` | один раз | слой HIGGS начинает сталкиваться с Biped и BipedNoCC |
| `ForceWeaponCollisionEnabled(false/true)` | `:8262-8263` | один раз | оружие HIGGS сталкивается всегда, кроме ножен |
| `GetHandRigidBody/GetWeaponRigidBody` | `src/main.cpp:4263-4269` | каждый кадр | кеш тел для опознания |
| `GetGrabbedRigidBody/GetGrabbedObject` | `:4285-4292` | каждый кадр | что держит каждая рука |
| `GetGrabTransform` | `:4303-4304`, `4057` | каждый кадр и при хвате | смещение схваченной кости |
| `IsTwoHanding` | `:2245` | в каждом контакте-попадании | направление и скорость двуручного удара |
| `DisableHand/EnableHand` | `:3764-3782` | при нуле стамины | выронить тяжёлое |

Не используются: `AddDroppedCallback` (вместо него опрос «было-стало» `src/main.cpp:4306-4311`),
`AddCollisionCallback`, `AddPulledCallback`, `AddStart/StopTwoHandingCallback`, `IsHoldingObject`,
`GetFingerValues`, `Is/Disable/EnableWeaponCollision`, `CanGrabObject`, `AddPostVrik*`, `GetGrabbedNodeName`
(список HIGGS `include/higgsinterface001.h:18-130`).

Что PLANCK делает с ресурсами HIGGS помимо API:

| Действие | Где | Характер |
|---|---|---|
| Ставит телам рук и оружия HIGGS `HK_COLLIDABLE_QUALITY_KEYFRAMED_REPORTING` | `src/main.cpp:4244-4276` | прямая запись в чужое тело |
| Гасит контакты «рука/оружие HIGGS против руки/оружия HIGGS», чтобы не было лишней отдачи от этой смены качества | `src/main.cpp:2125-2133` | исправляет побочный эффект собственной записи |
| Слой HIGGS по умолчанию зашит числом `56`, дальше выводится из тела правой руки | `src/main.cpp:462`, `4278-4280` | нет API «номер слоя HIGGS» |
| Выключает штатное тело ближнего боя VR (`VRMeleeData.collisionNode`, бит фильтра 14) | `src/main.cpp:2760-2770` + заплатка `7931-7934` | HIGGS читает то же тело, чтобы построить своё оружие (HIGGS `src/hand.cpp:720-740`, `703-715`) |
| Опознаёт тела HIGGS сравнением указателей | `src/main.cpp:478-513` | хрупко при пересоздании тел между кадрами |

---

## 5. Отношения с VRIK

PLANCK не получает интерфейс VRIK. Всё знание о VRIK — флаг `g_isVrikPresent = GetModuleHandle("vrik")`
(`src/main.cpp:8217`), используемый в двух местах:

| Место | Что делает | Ресурс VRIK |
|---|---|---|
| `UpdateMeleeAlpha` `src/main.cpp:930-944` + `GetWeaponNode` `src/utils.cpp:1501-1512` | при VRIK берёт узел `WEAPON`/`SHIELD` скелета **третьего** лица и меняет его прозрачность | узлы тела, которое VRIK делает основным (комментарий `src/main.cpp:7276`) |
| `PlayerCharacter_Load3D_Hook` `src/main.cpp:7269-7322` | заменяет `WEAPON`, `WeaponSword`, `WeaponDagger`, `WeaponAxe`, `WeaponMace`, `SHIELD`, `WeaponBack` на `BSFadeNode`, чинит дерево костей и `BOM` | те же узлы; граф анимации держал старый адрес — порча памяти, чинится патчем 1.3.0 (`mods/PLANCK VR Lifetime and Collision Alpha Fix/README.md:8-22`) |

Чего PLANCK не знает о VRIK: где у VRIK холстеры (`IVrikInterface001::GetHolsterSlotInReach` и др.,
`local/vrik-re/api/vrikinterface001.h:57-74`), положение пальцев (`getFingerPos`, `:41`), смещение
камеры (`:46-52`). **Вывод:** удар рукой у пояса, где VRIK держит оружие в холстере, PLANCK может
посчитать попаданием, а VRIK — жестом доставания; согласования нет ни с одной стороны.

Порядок кадра: PLANCK читает позы в `PreVrikPreHiggs` (`src/main.cpp:4033-4050`), то есть до IK VRIK;
попадания же считает по телам HIGGS, которые HIGGS ставит после VRIK. **Вывод:** для скорости руки
PLANCK берёт «сырую» руку, для точки удара — руку после VRIK и HIGGS.

---

## 6. Инвентарь ресурсов (сводно)

Префиксы — по общему словарю, чтобы таблица соединялась со списками HIGGS и VRIK.

| Ресурс | Доступ | Где | Когда |
|---|---|---|---|
| `collision:8 Biped layer bitfield (world filter)` | write | `src/main.cpp:4399-4426` | смена мира |
| `collision:33 BipedNoCC layer bitfield` | write | `src/main.cpp:4428-4433` | смена мира |
| `collision:56 HIGGS layer bitfield (+Biped,+BipedNoCC)` | write | `src/main.cpp:8257-8260` | PostPostLoad |
| `collision:filter bit14 (0x4000) of vanilla VRMeleeData collision body` | write | `src/main.cpp:2760-2770` | каждый шаг физики |
| `collision:32 DeadBip — перенос не-рэгдолл тел бипеда` | write | `src/main.cpp:1774-1775`, `2483-2508` | добавление тела |
| `collision:group sets (active biped / hittable CC / self-collide / no-player-collide)` | own | `src/main.cpp:445-448` | каждый кадр |
| `havok:contact listener + post-sim + entity listener on bhkWorld` | own | `src/main.cpp:4384-4395`, `4585-4597` | смена мира, каждый кадр |
| `havok:HIGGS hand/weapon rigid body quality type` | write | `src/main.cpp:4244-4276` | каждый кадр |
| `havok:player char proxy shape and capsule` | write | `src/main.cpp:4457-4568` | смена прокси |
| `havok:NPC ragdoll in world, constraints, motors, gravity` | own | `src/main.cpp:3438-3603`, `3153-3204`, `3646-3709` | вход в радиус |
| `havok:hkpCharacterProxy listener (player)` | own | `src/main.cpp:4444-4450`, `2548-2621` | смена прокси |
| `node:WEAPON/SHIELD… 3rd-person → BSFadeNode (VRIK body)` | write | `src/main.cpp:7269-7322` | Load3D игрока |
| `node:WEAPON/SHIELD fade alpha` | write | `src/main.cpp:930-944` | каждый кадр |
| `node:LeftWandNode/RightWandNode local transform` | read | `src/main.cpp:4037-4046`, `include/utils.h:98` | PreVrikPreHiggs |
| `node:1st-person hand bones world transform` | read | `src/main.cpp:4048`, `src/utils.cpp:1449-1455` | кадр |
| `node:HmdNode world transform` | read | `src/main.cpp:1280`, `src/utils.cpp:1477-1495` | кадр |
| `node:Left/RightMeleeWeaponOffsetNode old world transform` | read | `src/main.cpp:2255-2259` | контакт |
| `anim:staggerMagnitude/staggerDirection/staggerStart` | write | `src/main.cpp:599-615` | толчок |
| `anim:IsBlocking (player, in HitData populate)` | write | `src/main.cpp:5860-5865` | не срабатывает (заглушка) |
| `anim:bAllowRotation, IsBashing (spoof for Papyrus)` | patch | `src/main.cpp:5911-5937` | чтение из Papyrus |
| `anim:NPC_BumpFromFront/… events` | read | `src/main.cpp:8117-8134` | каждое событие графа |
| `equip:player attackState / attackData` | write | `src/main.cpp:1186`, `1241`, `1267`, `1328`, `1376-1378`, `1601` | замах и удар |
| `equip:player+0x6BC/+0x6C8 last hit position/velocity` | write | `src/main.cpp:1605-1609`, `1699-1703` | удар |
| `setting:player SpeedMult/CarryWeight (temporary AV)` | write | `src/utils.cpp:1100-1109`, `src/main.cpp:3844-3851` | переноска |
| `setting:player Stamina AV` | write | `src/main.cpp:990-1006`, `3857`, `3882-3917` | замах, переноска, толчок |
| `setting:fMinSoundVel` | write | `src/main.cpp:2072`, `4992`, `2358` | контакт рэгдоллов |
| `setting:activeragdoll.ini [Settings]` | own | `src/config.cpp:189-590` | старт |
| `input:controller velocity (OpenVR poses)` | read | `src/main.cpp:7978-8052` | каждый опрос поз |
| `input:joystick axes` | read | `src/main.cpp:8056-8090` | состояние контроллера |
| `input:trigger held (PlayerControls)` | read | `src/main.cpp:1177` | замах |
| `haptics:game PlayRumble (0xC59440)` | call | `src/RE/offsets.cpp:362`, `src/main.cpp:1592`, `1613`, `3963-3969`, `src/utils.cpp:1112-1124` | удар, толчок |
| `event:TESHitEvent (dispatch & replace)` | patch | `src/main.cpp:124-125`, `5883-5909` | удар |
| `event:TESCellAttachDetachEvent` | read | `src/main.cpp:8171-8188`, `8209-8210` | выгрузка ячейки |
| `event:MenuOpenCloseEvent` | read | `src/main.cpp:8204-8206` | меню |
| `form:ActorTypeAnimal, ActorTypeNPC keywords` | read | `src/main.cpp:8197-8202` | DataLoaded |
| `form:dialogue topic infos (shove/aggression/ragdoll)` | call | `src/main.cpp:2842-2895`, `4061-4077` | реакции NPC |

Перехваты и заплатки — таблица 1.2.

---

## 7. Дублирование механик

| Механика | PLANCK | Второй держатель | Что предлагается |
|---|---|---|---|
| Скорость контроллеров из OpenVR | `src/main.cpp:7978-8052`, `351-417` | HIGGS `src/main.cpp:168-188`, `include/hand.h:83-84` | отдать из HIGGS `GetControllerVelocity(isLeft, frames)` |
| «Отпустил предмет» | опрос `src/main.cpp:4306-4311` | HIGGS `AddDroppedCallback` `include/higgsinterface001.h:26` | подписка |
| Узел схваченной кости | `GetGrabbedNode` `src/main.cpp:645-660` | HIGGS `GetGrabbedNodeName` `include/higgsinterface001.h:130` | обновить копию заголовка |
| Отдача в контроллер | игровой `PlayRumble` `src/RE/offsets.cpp:362` | HIGGS `HapticsManager` поверх OpenVR `src/haptics.cpp:8-12`, `63-73` | один держатель отдачи |
| Столкновения своих рук и оружия | гасит контакты HIGGS↔HIGGS `src/main.cpp:2125-2133` | HIGGS решает то же в своём фильтре (**вывод**, требует сверки агентом HIGGS) | правило в одном месте |
| Прозрачность оружия ближнего боя | своя, штатная выключена `src/main.cpp:930-944`, `7577-7580` | игра | держатель — PLANCK, но API для HIGGS/VRIK нет |
| Тело оружия ближнего боя | выключает штатное `src/main.cpp:2760-2770` | HIGGS строит своё по его форме (`src/hand.cpp:720-740`) | договор о владении телом `VRMeleeData` |
| Проверка присутствия VRIK | `GetModuleHandle("vrik")` `src/main.cpp:8217` | VRIK отдаёт `IVrikInterface001` | получать интерфейс, а не имя модуля |

---

## 8. Горячие точки производительности

| Где | Что дорого | Оценка | Что можно сделать |
|---|---|---|---|
| `contactPointCallback` `src/main.cpp:1967-2327` | на каждый контакт мира: `GetRefFromCollidable` до 4 раз, `DYNAMIC_CAST`, `IsActiveActor` с `shared_mutex` (`1999`, `2024`), дорогие ветки бипедов идут **до** раннего выхода «нет тела HIGGS» (`2113`) | контакты рэгдоллов между собой идут сотнями за шаг | сначала дешёвые проверки слоёв и «есть ли тело HIGGS», ref — один раз |
| `IsRagdollCollisionIgnored` в контакте бипед-бипед | `std::mutex` дважды на контакт `src/main.cpp:2082`, `src/pluginapi.cpp:109-112` | множество почти всегда пусто | атомарный счётчик размера и ранний выход |
| `postSimulationCallback` `src/main.cpp:2354-2481` | `std::map` пар тел, двойной поиск `count`+`[]` (`2366-2374`), полный обход с `GetRefFromCollidable` каждый шаг | линейно по числу активных касаний | `unordered_map`, один поиск |
| `CollisionFilterComparisonCallback` `src/main.cpp:2625-2746` | до 4 `unordered_set<UInt16>::count` на пару | «сотни раз за кадр» по HIGGS `include/higgsinterface001.h:79` | битовые множества на 65536 групп (8 КБ) |
| Цикл по актёрам `src/main.cpp:4637-4806` | на актёра: `IsAddedToWorld`+`IsAddableToWorld` берут `updateLock` графа (`3083-3151`), `std::set<std::string>` рас по `editorId` (`3118-3121`), мьютексы исключений, `VectorLength` дважды (`4723-4724`), `DisableOrEnableSyncOnUpdate` каждый кадр каждому активному (`4778`) | на всех `actorsHigh` | кешировать «добавляем ли» по актёру, сравнивать квадраты расстояний |
| `UpdateMeleeAlpha` `src/main.cpp:930-944` | дважды за кадр `GetObjectByName` (`src/utils.cpp:1501-1512`) и рекурсивный `NiAVObject_SetFadeNodeRecurse` даже при альфе 1 | каждый кадр | кешировать узел, писать только при изменении |
| `ControllerStateCB` `src/main.cpp:8056-8090` | `GetInt32TrackedDeviceProperty` по каждой оси при каждом опросе; `(*g_openVR)->vrSystem` разыменован до проверки `g_openVR` (`8062-8066` против `8067`) | каждый опрос контроллера | кешировать индекс оси; порядок проверки — ошибка |
| `NotifyAnimationGraph_Hook` `src/main.cpp:8117-8134` | 4 сравнения строк на **каждое** принятое событие графа у всех персонажей | все NPC | сравнивать указатели `BSFixedString` |
| `Character_ModifyMovementData_Hook` `src/main.cpp:6236-6323` | `IsDoingGrabbedActorMovement` берёт мьютекс на каждого NPC каждый кадр (`704-708`) | все NPC | атомарный флаг «кто-то схвачен» |
| `GetStress/GetAnimPreLookAtPose/GetBoneDisplacement` `src/main.cpp:714-795` | линейный поиск кости по телу, `shared_lock` | при хвате | индекс тела в `ActiveRagdoll` |
| Опрос HIGGS `UpdateHiggsInfo` `src/main.cpp:4261-4312` | 10 вызовов через vtable каждый кадр | мелко | события HIGGS вместо опроса |
| `ReadConfigOptions` `src/config.cpp:189-590` | около 300 чтений ini через `GetPrivateProfileString` | только старт | — |

---

## 9. Что из этого следует для «трёх частей одного целого» (предложения)

Это предложения исследования, не решения; каждое опирается на строки выше.

1. **Разделить владение.** HIGGS — владелец тел рук, оружия и схваченного, их слоя и качества;
   PLANCK — владелец рэгдоллов NPC, попаданий и реакций NPC; VRIK — владелец тела игрока, холстеров,
   пальцев. Тогда запись PLANCK в качество тел HIGGS (`src/main.cpp:4244-4276`) и в маску слоя HIGGS
   (`8257-8260`) превращается в просьбу к HIGGS через API («хочу отчёты о контактах тел рук»,
   «хочу столкновение со слоем Biped»), а подмена узлов VRIK (`7269-7322`) — в просьбу к VRIK.
2. **Одно событие попадания с полным составом** в C++ (колбэк до и после): атакующий, цель, рука,
   тело-ударник (оружие/рука/схваченное — из HIGGS), тело-цель и узел, вид (укол/кулак/мах/щит),
   силовой, двуручный, скорость, импульс, урон, смертельный; колбэк «до» может отменить или
   масштабировать. Papyrus — событие `OnPlanckHit` с теми же полями.
3. **События механик**: толчок, рывок, опрокидывание, шатание, агрессия (смена ступени),
   рэгдолл вошёл/вышел из активных, подъём.
4. **Запросы по руке и по актёру**: касается ли рука актёра, идёт ли замах/силовой, скорость
   контроллера (у HIGGS), активен ли рэгдолл, стресс кости.
5. **Ревизия интерфейса 002** с версией структуры в событии вместо магии в `flags`.
6. **Снять дубли**: скорость контроллеров и отдача — одна точка (HIGGS), `AddDroppedCallback`
   вместо опроса, `GetGrabbedNodeName` вместо своего поиска.
7. **Недостающие механики, которые естественно замыкают тройку**: физическое блокирование ударов NPC
   (заглушка `src/main.cpp:5846-5849`) и тела оружия NPC (закомментировано `5464-5566`) — это как раз
   место, где тела оружия HIGGS должны встретиться с оружием NPC PLANCK.
