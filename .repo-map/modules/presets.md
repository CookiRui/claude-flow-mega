# Module: presets (L1)

Generated: 2026-03-30 | Files: 26 | Symbols: 187

## presets/unity/unity-runtime/Scripts/Gameplay/AutoTest/AutoTestBridge.cs

- `class` **AutoTestBridge** L9 (3 refs)
- `method` **Awake** L17
- `method` **LateUpdate** L30
- `method` **OnDestroy** L35
- `method` **SetMovementInput** L43
- `method` **PressButton** L48 (1 refs)
- `method` **ReleaseButton** L53 (1 refs)
- `method` **FindGameObject** L60

## presets/unity/unity-runtime/Scripts/Gameplay/AutoTest/IInputProvider.cs

- `interface` **IInputProvider** L9

## presets/unity/unity-runtime/Scripts/Gameplay/AutoTest/TestInputProvider.cs

- `class` **TestInputProvider** L11 (2 refs)
- `method` **SetMovement** L18
- `method` **PressButton** L20 (1 refs)
- `method` **ReleaseButton** L26 (1 refs)
- `method` **ClearFrameState** L35
- `method` **GetMovementInput** L41
- `method` **GetButtonDown** L42 (1 refs)
- `method` **GetButtonUp** L43 (1 refs)
- `method` **GetButton** L44 (1 refs)
- `method` **Reset** L46

## presets/unity/unity-runtime/Scripts/Gameplay/AutoTest/UnityInputProvider.cs

- `class` **UnityInputProvider** L8
- `method` **GetMovementInput** L10
- `method` **GetButtonDown** L15 (1 refs)
- `method` **GetButtonUp** L16 (1 refs)
- `method` **GetButton** L17 (1 refs)

## presets/unity/unity-runtime/Scripts/Tests/Editor/SanityTests.cs

- `class` **SanityTests** L8
- `method` **TrueIsTrue** L11
- `method` **AssemblyReferencesWork** L17

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/AutoTestAttribute.cs

- `class` **AutoTestActionAttribute** L6 (1 refs)
- `class` **AutoTestConditionAttribute** L13 (1 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/LogCapture.cs

- `class` **LogCapture** L7 (4 refs)
- `method` **GetErrors** L36 (1 refs)
- `method` **OnLogMessage** L53 (2 refs)
- `method` **Clear** L68 (6 refs)
- `method` **Dispose** L70

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/TestAction.cs

- `class` **TestAction** L7 (2 refs)
- `method` **Configure** L19 (2 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/TestCase.cs

- `class` **TestCase** L5 (1 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/TestCondition.cs

- `class` **TestCondition** L5 (3 refs)
- `method` **Configure** L20 (2 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/TestStep.cs

- `class` **TestStep** L3 (6 refs)
- `enum` **FailPolicy** L18 (5 refs)
- `enum` **StepResult** L19 (13 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Core/TypeRegistry.cs

- `class` **TypeRegistry** L8 (2 refs)
- `method` **EnsureInitialized** L24 (4 refs)
- `method` **ScanAssemblies** L31 (1 refs)
- `method` **CreateAction** L71
- `method` **CreateCondition** L79

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Results/TestResultBuilder.cs

- `class` **TestResultBuilder** L7
- `method` **Build** L9
- `method` **AppendPhase** L55 (2 refs)
- `method` **AppendSteps** L65 (2 refs)
- `method` **AppendSummary** L93 (1 refs)
- `method` **AppendErrors** L120 (1 refs)
- `method` **AppendContextDict** L136 (2 refs)
- `method` **AppendValue** L150 (2 refs)
- `method` **AppendString** L204 (12 refs)
- `method` **AppendNumber** L209 (11 refs)
- `method` **AppendNumber** L214 (11 refs)
- `method` **EscapeJson** L219 (10 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Runner/AutoTestRunner.cs

- `class` **AutoTestRunner** L9 (5 refs)
- `method` **RunSingleStep** L51 (1 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Runner/JsonTestCaseParser.cs

- `class` **JsonTestCaseParser** L8
- `method` **Parse** L10 (9 refs)
- `method` **ParseStep** L72 (1 refs)
- `method` **ParseAction** L117 (1 refs)
- `method` **ParseCondition** L145 (2 refs)
- `method` **ConvertJToken** L172 (4 refs)
- `method` **SubstituteParameters** L199 (1 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/AutoTest/Runner/TestOrchestrator.cs

- `class` **TestOrchestrator** L10
- `method` **Execute** L12 (3 refs)
- `method` **ComputeStatus** L120 (1 refs)
- `class` **TestResultData** L136 (2 refs)
- `class` **PhaseResult** L150 (4 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/BatchModePaths.cs

- `class` **BatchModePaths** L11 (6 refs)
- `method` **EnsureDirectories** L24 (1 refs)
- `method` **CleanupBeforeRun** L33 (2 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/BatchPlayModeRunner.cs

- `class` **BatchPlayModeRunner** L14 (16 refs)
- `method` **Run** L16 (1 refs)
- `method` **RunTest** L42 (1 refs)
- `method` **GetArgValue** L124 (4 refs)
- `method` **GetVarArgs** L135 (1 refs)
- `method` **SerializeVars** L152 (1 refs)
- `method` **EscapeJson** L168 (10 refs)
- `method` **EnsureScene** L174 (2 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/BatchResultWriter.cs

- `class` **BatchResultWriter** L11 (6 refs)
- `method` **WriteResult** L13 (2 refs)
- `method` **WriteError** L31 (3 refs)
- `method` **EscapeJson** L38 (10 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/PlayModeTestLauncher.cs

- `class` **PlayModeTestLauncher** L16 (23 refs)
- `method` **SaveSmokeTestAndEnterPlayMode** L61 (1 refs)
- `method` **SaveAutoTestAndEnterPlayMode** L79
- `method` **IsGameReady** L95 (2 refs)
- `method` **HasPendingCommand** L100 (3 refs)
- `method` **OnPlayModeChanged** L105 (1 refs)
- `method` **WaitForPlayMode** L120 (5 refs)
- `method` **TryStartPollingIfNeeded** L145 (2 refs)
- `method` **StartPolling** L154 (2 refs)
- `method` **PollGameReady** L162 (2 refs)
- `method` **PollGameReadyInternal** L180 (1 refs)
- `method` **StopPolling** L217 (3 refs)
- `method` **ExecutePendingCommand** L223 (1 refs)
- `method` **ExecuteAutoTest** L268 (2 refs)
- `method` **ClearPendingCommand** L311 (3 refs)
- `method` **FailPendingCommandAndCleanup** L317 (5 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/UnityOps/Handlers/AssetHandler.cs

- `class` **AssetHandler** L13 (7 refs)
- `method` **Execute** L15 (3 refs)
- `method` **CreateMaterial** L26 (1 refs)
- `method` **CreateFolder** L86 (3 refs)
- `method` **ListAssets** L115 (1 refs)
- `method` **ApplyMaterialProperties** L147 (1 refs)
- `method` **ApplyMaterialProperty** L162 (1 refs)
- `method` **NormalizePath** L220 (18 refs)
- `method` **AssetExists** L222 (16 refs)
- `method` **EnsureParentFolder** L227 (3 refs)
- `class` **AssetInfo** L243 (2 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/UnityOps/Handlers/PrefabHandler.cs

- `class` **PrefabHandler** L12 (12 refs)
- `method` **Execute** L14 (3 refs)
- `method` **CreatePrefab** L30 (1 refs)
- `method` **EditPrefab** L63 (1 refs)
- `method` **ListPrefabs** L131 (1 refs)
- `method` **PrefabAddComponent** L148 (1 refs)
- `method` **PrefabRemoveComponent** L188 (1 refs)
- `method` **PrefabModifyComponent** L245 (1 refs)
- `method` **PrefabListComponents** L292 (1 refs)
- `method` **PrefabInspectComponent** L319 (1 refs)
- `method` **BuildGameObject** L382 (7 refs)
- `method` **FindTargetInPrefab** L426 (5 refs)
- `method` **ApplyModifications** L438 (2 refs)
- `method` **BuildComponentList** L469 (2 refs)
- `method` **GetComponentTypeNames** L493 (6 refs)
- `method` **SetComponentProperties** L503 (2 refs)
- `method` **SetSerializedPropertyValue** L519 (2 refs)
- `method` **GetSerializedPropertyValue** L538 (2 refs)
- `method` **ResolveComponentType** L551 (12 refs)
- `method` **FindChildByName** L574 (4 refs)
- `method` **NormalizePath** L588 (18 refs)
- `method` **AssetExists** L590 (16 refs)
- `method` **EnsureParentFolder** L595 (3 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/UnityOps/Handlers/SceneHandler.cs

- `class` **SceneHandler** L14 (13 refs)
- `method` **Execute** L16 (3 refs)
- `method` **CreateScene** L32 (1 refs)
- `method` **EditScene** L71 (1 refs)
- `method` **ListScenes** L139 (1 refs)
- `method` **SceneAddComponent** L150 (1 refs)
- `method` **SceneRemoveComponent** L184 (1 refs)
- `method` **SceneModifyComponent** L235 (1 refs)
- `method` **SceneListComponents** L276 (1 refs)
- `method` **SceneInspectComponent** L296 (1 refs)
- `method` **BuildGameObject** L353 (7 refs)
- `method` **FindSceneGameObject** L397 (5 refs)
- `method` **ApplyModifications** L419 (2 refs)
- `method` **BuildComponentList** L459 (2 refs)
- `method` **GetComponentTypeNames** L483 (6 refs)
- `method` **SetComponentProperties** L493 (2 refs)
- `method` **SetSerializedPropertyValue** L509 (2 refs)
- `method` **GetSerializedPropertyValue** L528 (2 refs)
- `method` **ResolveComponentType** L541 (12 refs)
- `method` **AddSceneToBuildSettings** L567 (1 refs)
- `method` **NormalizePath** L578 (18 refs)
- `method` **AssetExists** L580 (16 refs)
- `method` **EnsureParentFolder** L585 (3 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/UnityOps/IUnityOpsHandler.cs

- `interface` **IUnityOpsHandler** L7 (1 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/UnityOps/UnityOpsCommand.cs

- `class` **OpsCommandEnvelope** L9 (19 refs)
- `class` **OpsResult** L18 (114 refs)
- `method` **Success** L27 (17 refs)
- `method` **Error** L40 (68 refs)
- `class` **CreateSceneParams** L56
- `class` **EditSceneParams** L64
- `class` **SceneOperation** L71 (2 refs)
- `class` **CreatePrefabParams** L79
- `class` **EditPrefabParams** L86
- `class` **CreateMaterialParams** L93
- `class` **CreateFolderParams** L101
- `class` **ListAssetsParams** L107 (1 refs)
- `class` **ComponentOperationParams** L116 (4 refs)
- `class` **AddComponentParams** L123
- `class` **RemoveComponentParams** L129
- `class` **ModifyComponentParams** L136
- `class` **InspectComponentParams** L144
- `class` **GameObjectDesc** L153 (6 refs)
- `class` **TransformDesc** L165 (1 refs)
- `class` **ComponentDesc** L173 (2 refs)

## presets/unity/unity-runtime/Scripts/Tools/Editor/BatchMode/UnityOps/UnityOpsRunner.cs

- `class` **UnityOpsRunner** L15
- `method` **Run** L40 (1 refs)
- `method` **GetCommandFilePath** L89 (1 refs)
- `method` **WriteResultAndExit** L100 (3 refs)
- `method` **WriteErrorAndExit** L110 (4 refs)
