using System;
using System.IO;
using UnityEngine;

namespace {root-namespace}.Tools.BatchMode
{
    /// <summary>
    /// Path resolver for batch mode file I/O.
    /// Root directory: .claude/batch-mode/ (relative to the Unity project root).
    /// </summary>
    public static class BatchModePaths
    {
        public static readonly string RootDir;
        public static readonly string ResultsDir;

        static BatchModePaths()
        {
            // Application.dataPath = "<ProjectRoot>/Assets"
            var projectRoot = Path.GetDirectoryName(Application.dataPath);
            RootDir = Path.Combine(projectRoot, ".claude", "batch-mode");
            ResultsDir = Path.Combine(RootDir, "results");
        }

        public static void EnsureDirectories()
        {
            Directory.CreateDirectory(RootDir);
            Directory.CreateDirectory(ResultsDir);
        }

        /// <summary>
        /// Clean up previous result files before a new run.
        /// </summary>
        public static void CleanupBeforeRun()
        {
            try
            {
                if (Directory.Exists(ResultsDir))
                {
                    foreach (var file in Directory.GetFiles(ResultsDir))
                        File.Delete(file);
                }
            }
            catch (Exception)
            {
                // Silent cleanup failure is acceptable
            }
        }
    }
}
