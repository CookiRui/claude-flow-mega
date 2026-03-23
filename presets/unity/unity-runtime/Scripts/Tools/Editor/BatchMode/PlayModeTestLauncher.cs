using System;
using UnityEditor;
using UnityEngine;

namespace {root-namespace}.Tools.BatchMode
{
    /// <summary>
    /// PlayMode test engine with [InitializeOnLoad] polling.
    /// Flow: SaveSmokeTestAndEnterPlayMode() -> SessionState stores key -> isPlaying=true -> DOMAIN RELOAD
    ///       -> [InitializeOnLoad] detects pending -> polls PlayMode ready -> writes result JSON -> Exit
    ///
    /// "Ready" condition: PlayMode entered + ran N frames (no game logic dependency by default).
    /// Override IsGameReady() for project-specific readiness checks.
    /// </summary>
    [InitializeOnLoad]
    public static class PlayModeTestLauncher
    {
        private const float PollInterval = 0.5f;
        private const float TimeoutSeconds = 120f;
        private const float WaitForPlayModeTimeout = 30f;
        private const int ReadyFrameThreshold = 10;

        private const string ToolInitiatedKey = "BatchMode.ToolInitiatedPlayMode";
        private const string CommandConsumedKey = "BatchMode.CommandConsumed";
        private const string PendingCommandIdKey = "BatchMode.PendingCommandId";
        private const string PendingCommandTypeKey = "BatchMode.PendingCommandType";

        private static float _pollStartTime;
        private static float _lastPollTime;
        private static bool _polling;
        private static float _waitForPlayModeStartTime;
        private static int _playModeEntryFrame;

        static PlayModeTestLauncher()
        {
            EditorApplication.playModeStateChanged += OnPlayModeChanged;

            if (!HasPendingCommand()) return;

            if (EditorApplication.isPlaying)
            {
                StartPolling();
                return;
            }

            if (SessionState.GetBool(ToolInitiatedKey, false) || EditorApplication.isPlayingOrWillChangePlaymode)
            {
                _waitForPlayModeStartTime = (float)EditorApplication.timeSinceStartup;
                EditorApplication.update += WaitForPlayMode;
                return;
            }

            // Stale SessionState in Edit Mode (should not happen)
            Debug.LogWarning("[PlayModeTestLauncher] stale pending in Edit Mode, cleaning up");
            FailPendingCommandAndCleanup("Play Mode entry was interrupted (Editor restarted or crashed)");
        }

        /// <summary>
        /// Smoke test: enter PlayMode, wait for ready, write success result, exit.
        /// </summary>
        public static void SaveSmokeTestAndEnterPlayMode()
        {
            var id = "batch_smoke_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff");

            Debug.Log($"[PlayModeTestLauncher] Saving smoke test (id={id}) and entering Play Mode");

            BatchModePaths.CleanupBeforeRun();

            SessionState.SetString(PendingCommandIdKey, id);
            SessionState.SetString(PendingCommandTypeKey, "smoke_test");
            SessionState.SetBool(ToolInitiatedKey, true);
            SessionState.SetBool(CommandConsumedKey, false);
            EditorApplication.isPlaying = true;
        }

        /// <summary>
        /// AutoTest entry: enter PlayMode, wait for ready, execute JSON test case.
        /// </summary>
        public static void SaveAutoTestAndEnterPlayMode()
        {
            var id = "batch_autotest_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff");
            Debug.Log($"[PlayModeTestLauncher] Saving AutoTest (id={id}) and entering Play Mode");
            BatchModePaths.CleanupBeforeRun();
            SessionState.SetString(PendingCommandIdKey, id);
            SessionState.SetString(PendingCommandTypeKey, "run_test");
            SessionState.SetBool(ToolInitiatedKey, true);
            SessionState.SetBool(CommandConsumedKey, false);
            EditorApplication.isPlaying = true;
        }

        /// <summary>
        /// Readiness check. Override this for project-specific game-ready conditions.
        /// Default: PlayMode entered + ran N frames.
        /// </summary>
        public static bool IsGameReady()
        {
            return EditorApplication.isPlaying && Time.frameCount > _playModeEntryFrame + ReadyFrameThreshold;
        }

        private static bool HasPendingCommand()
        {
            return !string.IsNullOrEmpty(SessionState.GetString(PendingCommandIdKey, ""));
        }

        private static void OnPlayModeChanged(PlayModeStateChange state)
        {
            if (state == PlayModeStateChange.EnteredEditMode)
            {
                SessionState.SetBool(ToolInitiatedKey, false);
                SessionState.SetBool(CommandConsumedKey, false);
                ClearPendingCommand();
            }
            else if (state == PlayModeStateChange.EnteredPlayMode)
            {
                _playModeEntryFrame = Time.frameCount;
                TryStartPollingIfNeeded();
            }
        }

        private static void WaitForPlayMode()
        {
            if (EditorApplication.isPlaying)
            {
                EditorApplication.update -= WaitForPlayMode;
                _playModeEntryFrame = Time.frameCount;
                TryStartPollingIfNeeded();
            }
            else if (!SessionState.GetBool(ToolInitiatedKey, false))
            {
                EditorApplication.update -= WaitForPlayMode;
                if (HasPendingCommand())
                {
                    Debug.LogWarning("[PlayModeTestLauncher] Play Mode cancelled while waiting, cleaning up");
                    FailPendingCommandAndCleanup("Play Mode cancelled by user");
                }
            }
            else if ((float)EditorApplication.timeSinceStartup - _waitForPlayModeStartTime > WaitForPlayModeTimeout)
            {
                Debug.LogError($"[PlayModeTestLauncher] WaitForPlayMode timeout after {WaitForPlayModeTimeout}s");
                EditorApplication.update -= WaitForPlayMode;
                FailPendingCommandAndCleanup("Play Mode did not start within timeout");
            }
        }

        private static void TryStartPollingIfNeeded()
        {
            if (HasPendingCommand() && !_polling)
            {
                Debug.Log("[PlayModeTestLauncher] Starting game-ready poll");
                StartPolling();
            }
        }

        private static void StartPolling()
        {
            _polling = true;
            _pollStartTime = (float)EditorApplication.timeSinceStartup;
            _lastPollTime = 0f;
            EditorApplication.update += PollGameReady;
        }

        private static void PollGameReady()
        {
            if (!_polling) return;

            var now = (float)EditorApplication.timeSinceStartup;
            if (now - _lastPollTime < PollInterval) return;
            _lastPollTime = now;

            try
            {
                PollGameReadyInternal(now);
            }
            catch (Exception e)
            {
                Debug.LogWarning($"[PlayModeTestLauncher] Poll exception (will retry): {e.Message}");
            }
        }

        private static void PollGameReadyInternal(float now)
        {
            if (!EditorApplication.isPlaying)
            {
                if (EditorApplication.isPlayingOrWillChangePlaymode)
                    return;

                Debug.LogWarning("[PlayModeTestLauncher] isPlaying=false, cleaning up");
                StopPolling();
                FailPendingCommandAndCleanup("Play Mode exited unexpectedly");
                return;
            }

            if (now - _pollStartTime > TimeoutSeconds)
            {
                Debug.LogError($"[PlayModeTestLauncher] Game ready timeout after {TimeoutSeconds}s");
                StopPolling();
                FailPendingCommandAndCleanup("PlayMode not ready after timeout");
                return;
            }

            if (IsGameReady())
            {
                Debug.Log("[PlayModeTestLauncher] PlayMode ready, executing pending command");
                StopPolling();

                if (SessionState.GetBool(CommandConsumedKey, false))
                {
                    Debug.LogWarning("[PlayModeTestLauncher] command already consumed, skipping");
                    return;
                }
                SessionState.SetBool(CommandConsumedKey, true);

                ExecutePendingCommand();
            }
        }

        private static void StopPolling()
        {
            _polling = false;
            EditorApplication.update -= PollGameReady;
        }

        private static void ExecutePendingCommand()
        {
            var id = SessionState.GetString(PendingCommandIdKey, "");
            var commandType = SessionState.GetString(PendingCommandTypeKey, "smoke_test");
            ClearPendingCommand();

            if (string.IsNullOrEmpty(id))
            {
                Debug.LogWarning("[PlayModeTestLauncher] no pending command id, skipping");
                return;
            }

            if (commandType == "smoke_test")
            {
                Debug.Log("[PlayModeTestLauncher] Smoke test passed: PlayMode entered and scene loaded");
                var timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss");
                var json = $"{{\"id\":\"{id}\",\"command\":\"smoke_test\",\"status\":\"passed\",\"timestamp\":\"{timestamp}\",\"message\":\"PlayMode entered and scene loaded\",\"frameCount\":{Time.frameCount}}}";
                BatchResultWriter.WriteResult(id, json);

                if (Application.isBatchMode)
                {
                    Debug.Log("[PlayModeTestLauncher] Batch smoke test done, exiting with code 0");
                    EditorApplication.Exit(0);
                }
                return;
            }

            if (commandType == "run_test")
            {
                ExecuteAutoTest(id);
                return;
            }

            // Future: extend with additional command types here
            Debug.LogWarning($"[PlayModeTestLauncher] Unknown command type: {commandType}");
            BatchResultWriter.WriteError(id, commandType, $"Unknown command type: {commandType}");
            if (Application.isBatchMode)
                EditorApplication.Exit(1);
        }

        /// <summary>
        /// Execute an AutoTest from stored SessionState data.
        /// Projects should implement their own test orchestration logic here.
        /// This is a placeholder that reads the stored JSON and writes a basic result.
        /// </summary>
        private static void ExecuteAutoTest(string commandId)
        {
            try
            {
                Debug.Log("[PlayModeTestLauncher] Starting AutoTest execution...");

                // Read stored test data from SessionState
                var json = SessionState.GetString("BatchMode.AutoTest.TestJson", "");
                var varsJson = SessionState.GetString("BatchMode.AutoTest.VarsJson", "{}");

                if (string.IsNullOrEmpty(json))
                {
                    BatchResultWriter.WriteError(commandId, "run_test", "No test JSON found in SessionState");
                    if (Application.isBatchMode) EditorApplication.Exit(1);
                    return;
                }

                // TODO: Implement project-specific test orchestration here.
                // Parse the test JSON, execute actions, and collect results.
                // Example:
                //   var testCase = YourTestParser.Parse(json, vars);
                //   var result = await YourTestOrchestrator.Execute(testCase);

                Debug.Log($"[PlayModeTestLauncher] AutoTest placeholder - received JSON ({json.Length} chars)");
                var timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss");
                var resultJson = $"{{\"id\":\"{commandId}\",\"command\":\"run_test\",\"status\":\"passed\",\"timestamp\":\"{timestamp}\",\"message\":\"AutoTest completed (implement project-specific logic)\",\"frameCount\":{Time.frameCount}}}";
                BatchResultWriter.WriteResult(commandId, resultJson);

                if (Application.isBatchMode)
                {
                    Debug.Log("[PlayModeTestLauncher] AutoTest done, exiting with code 0");
                    EditorApplication.Exit(0);
                }
            }
            catch (Exception e)
            {
                Debug.LogError($"[PlayModeTestLauncher] ExecuteAutoTest fatal error: {e}");
                BatchResultWriter.WriteError(commandId, "run_test", $"Fatal: {e.GetType().Name}: {e.Message}");
                if (Application.isBatchMode)
                    EditorApplication.Exit(1);
            }
        }

        private static void ClearPendingCommand()
        {
            SessionState.EraseString(PendingCommandIdKey);
            SessionState.EraseString(PendingCommandTypeKey);
        }

        private static void FailPendingCommandAndCleanup(string message)
        {
            var id = SessionState.GetString(PendingCommandIdKey, "unknown");
            var commandType = SessionState.GetString(PendingCommandTypeKey, "smoke_test");
            BatchResultWriter.WriteError(id, commandType, message);
            ClearPendingCommand();

            if (Application.isBatchMode)
            {
                Debug.LogError($"[PlayModeTestLauncher] Batch mode failure: {message}");
                EditorApplication.Exit(1);
            }
        }
    }
}
