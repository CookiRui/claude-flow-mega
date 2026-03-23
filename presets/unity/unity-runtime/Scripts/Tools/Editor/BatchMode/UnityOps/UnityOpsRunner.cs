using System;
using System.Collections.Generic;
using System.IO;
using Newtonsoft.Json;
using UnityEditor;
using UnityEngine;
using {root-namespace}.Tools.BatchMode.UnityOps.Handlers;

namespace {root-namespace}.Tools.BatchMode.UnityOps
{
    /// <summary>
    /// Entry point for Unity asset operations in batch mode.
    /// Reads a command JSON file (via --ops-command arg), dispatches to the appropriate handler.
    /// </summary>
    public static class UnityOpsRunner
    {
        private static readonly Dictionary<string, IUnityOpsHandler> Handlers = new Dictionary<string, IUnityOpsHandler>
        {
            { "create-scene", new SceneHandler() },
            { "edit-scene", new SceneHandler() },
            { "list-scenes", new SceneHandler() },
            { "scene-add-component", new SceneHandler() },
            { "scene-remove-component", new SceneHandler() },
            { "scene-modify-component", new SceneHandler() },
            { "scene-list-components", new SceneHandler() },
            { "scene-inspect-component", new SceneHandler() },
            { "create-prefab", new PrefabHandler() },
            { "edit-prefab", new PrefabHandler() },
            { "list-prefabs", new PrefabHandler() },
            { "prefab-add-component", new PrefabHandler() },
            { "prefab-remove-component", new PrefabHandler() },
            { "prefab-modify-component", new PrefabHandler() },
            { "prefab-list-components", new PrefabHandler() },
            { "prefab-inspect-component", new PrefabHandler() },
            { "create-material", new AssetHandler() },
            { "create-folder", new AssetHandler() },
            { "list-assets", new AssetHandler() },
        };

        public static void Run()
        {
            string commandFilePath = null;
            try
            {
                commandFilePath = GetCommandFilePath();
                if (string.IsNullOrEmpty(commandFilePath))
                {
                    WriteErrorAndExit("unknown", "unknown", "Missing --ops-command argument");
                    return;
                }

                if (!File.Exists(commandFilePath))
                {
                    WriteErrorAndExit("unknown", "unknown", $"Command file not found: {commandFilePath}");
                    return;
                }

                var json = File.ReadAllText(commandFilePath);
                var envelope = JsonConvert.DeserializeObject<OpsCommandEnvelope>(json);

                if (envelope == null || string.IsNullOrEmpty(envelope.Command))
                {
                    WriteErrorAndExit("unknown", "unknown", "Invalid command JSON: missing 'command' field");
                    return;
                }

                if (string.IsNullOrEmpty(envelope.Id))
                    envelope.Id = DateTime.Now.ToString("yyyyMMddHHmmss");

                Debug.Log($"[UnityOps] Executing command: {envelope.Command} (id={envelope.Id})");

                if (!Handlers.TryGetValue(envelope.Command, out var handler))
                {
                    WriteResultAndExit(OpsResult.Error(envelope.Id, envelope.Command,
                        $"Unknown command: {envelope.Command}"));
                    return;
                }

                var result = handler.Execute(envelope);
                WriteResultAndExit(result);
            }
            catch (Exception e)
            {
                Debug.LogError($"[UnityOps] Exception: {e}");
                WriteErrorAndExit("unknown", "unknown", $"Exception: {e.Message}");
            }
        }

        private static string GetCommandFilePath()
        {
            var args = Environment.GetCommandLineArgs();
            for (int i = 0; i < args.Length - 1; i++)
            {
                if (args[i] == "--ops-command")
                    return args[i + 1];
            }
            return null;
        }

        private static void WriteResultAndExit(OpsResult result)
        {
            var json = JsonConvert.SerializeObject(result, Formatting.Indented);
            BatchResultWriter.WriteResult("unity-ops", json);
            Debug.Log($"[UnityOps] Result: {json}");

            int exitCode = result.Status == "success" ? 0 : 1;
            EditorApplication.Exit(exitCode);
        }

        private static void WriteErrorAndExit(string id, string command, string message)
        {
            WriteResultAndExit(OpsResult.Error(id, command, message));
        }
    }
}
