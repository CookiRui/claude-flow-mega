using System;
using System.IO;
using UnityEngine;

namespace {root-namespace}.Tools.BatchMode
{
    /// <summary>
    /// Atomic JSON result writer for batch mode operations.
    /// Uses .tmp -> File.Move to ensure atomicity (no partial reads by external watchers).
    /// </summary>
    public static class BatchResultWriter
    {
        public static void WriteResult(string id, string json)
        {
            try
            {
                BatchModePaths.EnsureDirectories();
                var path = Path.Combine(BatchModePaths.ResultsDir, id + ".json");
                var tempPath = path + ".tmp";
                File.WriteAllText(tempPath, json);
                if (File.Exists(path))
                    File.Delete(path);
                File.Move(tempPath, path);
            }
            catch (Exception e)
            {
                Debug.LogError($"[BatchResultWriter] Error writing result '{id}': {e.Message}");
            }
        }

        public static void WriteError(string id, string command, string message)
        {
            var timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss");
            var json = $"{{\"id\":\"{EscapeJson(id)}\",\"command\":\"{EscapeJson(command)}\",\"status\":\"error\",\"timestamp\":\"{timestamp}\",\"message\":\"{EscapeJson(message)}\"}}";
            WriteResult(id, json);
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r");
        }
    }
}
