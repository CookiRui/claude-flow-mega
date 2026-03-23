using System.Collections.Generic;
using System.IO;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;

namespace {root-namespace}.Tools.BatchMode
{
    /// <summary>
    /// Batch mode entry points for PlayMode testing.
    /// Run() = smoke test (enter PlayMode, verify scene loads).
    /// RunTest() = AutoTest (enter PlayMode, execute JSON test case).
    /// </summary>
    public static class BatchPlayModeRunner
    {
        public static void Run()
        {
            if (!Application.isBatchMode)
            {
                Debug.LogError("[BatchPlayModeRunner] Must run in batch mode");
                EditorApplication.Exit(1);
                return;
            }

            string scenePath = GetArgValue("-scene");
            if (scenePath == null)
            {
                Debug.LogError("[BatchPlayModeRunner] Missing required -scene argument.");
                Debug.LogError("[BatchPlayModeRunner] Add to command line: -scene Assets/Scenes/<YourScene>.unity");
                Debug.LogError("[BatchPlayModeRunner] The value must be a relative path starting with Assets/, ending with .unity");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[BatchPlayModeRunner] Starting PlayMode smoke test with scene: {scenePath}");
            EnsureScene(scenePath);
            BatchModePaths.EnsureDirectories();
            BatchModePaths.CleanupBeforeRun();
            PlayModeTestLauncher.SaveSmokeTestAndEnterPlayMode();
        }

        public static void RunTest()
        {
            if (!Application.isBatchMode)
            {
                Debug.LogError("[BatchPlayModeRunner] Must run in batch mode");
                EditorApplication.Exit(1);
                return;
            }

            // Parse -testCase argument
            string testCasePath = GetArgValue("-testCase");
            if (string.IsNullOrEmpty(testCasePath))
            {
                Debug.LogError("[BatchPlayModeRunner] Missing required -testCase argument.");
                Debug.LogError("[BatchPlayModeRunner] Usage: -testCase <path.json> or -testCase stdin");
                EditorApplication.Exit(1);
                return;
            }

            // Read test case JSON
            string json;
            if (testCasePath == "stdin")
            {
                json = GetArgValue("-testJson");
                if (string.IsNullOrEmpty(json))
                {
                    Debug.LogError("[BatchPlayModeRunner] -testCase stdin requires -testJson <json_content>");
                    EditorApplication.Exit(1);
                    return;
                }
            }
            else
            {
                if (!File.Exists(testCasePath))
                {
                    Debug.LogError($"[BatchPlayModeRunner] Test case file not found: {testCasePath}");
                    EditorApplication.Exit(1);
                    return;
                }
                json = File.ReadAllText(testCasePath);
            }

            // Parse -scene (CLI overrides JSON)
            string scenePath = GetArgValue("-scene");

            // Parse -var key=value arguments
            var vars = GetVarArgs();

            // Try to extract scene from JSON if not provided via CLI
            if (string.IsNullOrEmpty(scenePath))
            {
                try
                {
                    var parsed = Newtonsoft.Json.Linq.JObject.Parse(json);
                    scenePath = parsed.Value<string>("scene");
                }
                catch { }
            }

            if (string.IsNullOrEmpty(scenePath))
            {
                Debug.LogError("[BatchPlayModeRunner] No scene specified. Use -scene or declare 'scene' in JSON.");
                EditorApplication.Exit(1);
                return;
            }

            Debug.Log($"[BatchPlayModeRunner] Starting AutoTest with scene: {scenePath}");
            Debug.Log($"[BatchPlayModeRunner] Test case: {testCasePath}");
            if (vars.Count > 0)
                Debug.Log($"[BatchPlayModeRunner] Variables: {vars.Count} overrides");

            EnsureScene(scenePath);
            BatchModePaths.EnsureDirectories();
            BatchModePaths.CleanupBeforeRun();

            // Store test data in SessionState for PlayModeTestLauncher
            SessionState.SetString("BatchMode.AutoTest.TestJson", json);
            SessionState.SetString("BatchMode.AutoTest.VarsJson", SerializeVars(vars));

            PlayModeTestLauncher.SaveAutoTestAndEnterPlayMode();
        }

        private static string GetArgValue(string argName)
        {
            string[] args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == argName)
                    return args[i + 1];
            }
            return null;
        }

        private static Dictionary<string, string> GetVarArgs()
        {
            var vars = new Dictionary<string, string>();
            string[] args = System.Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "-var")
                {
                    var kv = args[i + 1];
                    var eq = kv.IndexOf('=');
                    if (eq > 0)
                        vars[kv.Substring(0, eq)] = kv.Substring(eq + 1);
                }
            }
            return vars;
        }

        private static string SerializeVars(Dictionary<string, string> vars)
        {
            if (vars.Count == 0) return "{}";
            var sb = new System.Text.StringBuilder();
            sb.Append('{');
            bool first = true;
            foreach (var kvp in vars)
            {
                if (!first) sb.Append(',');
                first = false;
                sb.Append('"').Append(EscapeJson(kvp.Key)).Append("\":\"").Append(EscapeJson(kvp.Value)).Append('"');
            }
            sb.Append('}');
            return sb.ToString();
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r");
        }

        private static void EnsureScene(string scenePath)
        {
            var currentScene = EditorSceneManager.GetActiveScene();
            if (currentScene.path != scenePath)
            {
                Debug.Log($"[BatchPlayModeRunner] Opening scene: {scenePath}");

                var buildScenes = EditorBuildSettings.scenes;
                bool found = false;
                for (int i = 0; i < buildScenes.Length; i++)
                {
                    if (buildScenes[i].path == scenePath)
                    {
                        found = true;
                        break;
                    }
                }
                if (!found)
                {
                    var newScenes = new EditorBuildSettingsScene[buildScenes.Length + 1];
                    for (int i = 0; i < buildScenes.Length; i++)
                        newScenes[i] = buildScenes[i];
                    newScenes[buildScenes.Length] = new EditorBuildSettingsScene(scenePath, true);
                    EditorBuildSettings.scenes = newScenes;
                    Debug.Log($"[BatchPlayModeRunner] Added {scenePath} to Build Settings");
                }

                EditorSceneManager.OpenScene(scenePath);
            }
        }
    }
}
