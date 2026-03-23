using System.Collections.Generic;
using System.Text;
using UnityEngine;

namespace {root-namespace}.Tools.AutoTest
{
    public static class TestResultBuilder
    {
        public static string Build(TestResultData data)
        {
            var sb = new StringBuilder();
            sb.Append('{');

            AppendString(sb, "id", data.Id); sb.Append(',');
            AppendString(sb, "command", "run_test"); sb.Append(',');
            AppendString(sb, "status", data.Status); sb.Append(',');
            AppendString(sb, "timestamp", data.Timestamp); sb.Append(',');
            AppendNumber(sb, "duration", data.Duration); sb.Append(',');
            AppendString(sb, "testName", data.TestName); sb.Append(',');
            AppendString(sb, "scene", data.Scene ?? "");

            // Setup phase
            if (data.SetupPhase != null)
            {
                sb.Append(",\"setup\":");
                AppendPhase(sb, data.SetupPhase);
            }

            // Test steps
            sb.Append(",\"steps\":");
            AppendSteps(sb, data.TestSteps);

            // Cleanup phase
            if (data.CleanupPhase != null)
            {
                sb.Append(",\"cleanup\":");
                AppendPhase(sb, data.CleanupPhase);
            }

            // Summary
            sb.Append(",\"summary\":");
            AppendSummary(sb, data.TestSteps);

            // Captured errors
            if (data.CapturedErrors != null && data.CapturedErrors.Count > 0)
            {
                sb.Append(",\"capturedErrors\":");
                AppendErrors(sb, data.CapturedErrors);
            }

            sb.Append('}');
            return sb.ToString();
        }

        private static void AppendPhase(StringBuilder sb, PhaseResult phase)
        {
            sb.Append('{');
            AppendString(sb, "status", phase.Status); sb.Append(',');
            AppendNumber(sb, "duration", phase.Duration); sb.Append(',');
            sb.Append("\"steps\":");
            AppendSteps(sb, phase.Steps);
            sb.Append('}');
        }

        private static void AppendSteps(StringBuilder sb, List<AutoTestRunner.StepResultData> steps)
        {
            sb.Append('[');
            if (steps != null)
            {
                for (int i = 0; i < steps.Count; i++)
                {
                    if (i > 0) sb.Append(',');
                    var s = steps[i];
                    sb.Append('{');
                    AppendNumber(sb, "index", s.Index); sb.Append(',');
                    AppendString(sb, "name", s.Name); sb.Append(',');
                    AppendString(sb, "result", s.Result.ToString()); sb.Append(',');
                    AppendNumber(sb, "duration", s.Duration); sb.Append(',');
                    AppendString(sb, "message", s.Message ?? "");

                    if (s.Context != null && s.Context.Count > 0)
                    {
                        sb.Append(",\"context\":");
                        AppendContextDict(sb, s.Context);
                    }

                    sb.Append('}');
                }
            }
            sb.Append(']');
        }

        private static void AppendSummary(StringBuilder sb, List<AutoTestRunner.StepResultData> steps)
        {
            int total = 0, passed = 0, failed = 0, timeout = 0, skipped = 0;
            if (steps != null)
            {
                total = steps.Count;
                foreach (var s in steps)
                {
                    switch (s.Result)
                    {
                        case StepResult.Passed: passed++; break;
                        case StepResult.Failed: failed++; break;
                        case StepResult.Timeout: timeout++; break;
                        case StepResult.Skipped: skipped++; break;
                    }
                }
            }

            sb.Append('{');
            AppendNumber(sb, "total", total); sb.Append(',');
            AppendNumber(sb, "passed", passed); sb.Append(',');
            AppendNumber(sb, "failed", failed); sb.Append(',');
            AppendNumber(sb, "timeout", timeout); sb.Append(',');
            AppendNumber(sb, "skipped", skipped);
            sb.Append('}');
        }

        private static void AppendErrors(StringBuilder sb, List<LogCapture.LogEntry> errors)
        {
            sb.Append('[');
            for (int i = 0; i < errors.Count; i++)
            {
                if (i > 0) sb.Append(',');
                var e = errors[i];
                sb.Append('{');
                AppendString(sb, "type", e.Type.ToString()); sb.Append(',');
                AppendString(sb, "message", e.Message); sb.Append(',');
                AppendNumber(sb, "timestamp", e.Timestamp);
                sb.Append('}');
            }
            sb.Append(']');
        }

        private static void AppendContextDict(StringBuilder sb, Dictionary<string, object> dict)
        {
            sb.Append('{');
            bool first = true;
            foreach (var kvp in dict)
            {
                if (!first) sb.Append(',');
                first = false;
                sb.Append('"').Append(EscapeJson(kvp.Key)).Append("\":");
                AppendValue(sb, kvp.Value);
            }
            sb.Append('}');
        }

        private static void AppendValue(StringBuilder sb, object value)
        {
            if (value == null) { sb.Append("null"); return; }
            if (value is string s) { sb.Append('"').Append(EscapeJson(s)).Append('"'); return; }
            if (value is bool b) { sb.Append(b ? "true" : "false"); return; }
            if (value is float f) { sb.Append(f.ToString("F2")); return; }
            if (value is double d) { sb.Append(d.ToString("F2")); return; }
            if (value is int || value is long) { sb.Append(value); return; }
            if (value is Vector3 v3)
            {
                sb.Append('[').Append(v3.x.ToString("F4")).Append(',')
                  .Append(v3.y.ToString("F4")).Append(',')
                  .Append(v3.z.ToString("F4")).Append(']');
                return;
            }
            if (value is Quaternion q)
            {
                sb.Append('[').Append(q.x.ToString("F4")).Append(',')
                  .Append(q.y.ToString("F4")).Append(',')
                  .Append(q.z.ToString("F4")).Append(',')
                  .Append(q.w.ToString("F4")).Append(']');
                return;
            }
            if (value is Dictionary<string, object> dict)
            {
                AppendContextDict(sb, dict);
                return;
            }
            if (value is List<object> list)
            {
                sb.Append('[');
                for (int i = 0; i < list.Count; i++)
                {
                    if (i > 0) sb.Append(',');
                    AppendValue(sb, list[i]);
                }
                sb.Append(']');
                return;
            }
            if (value is List<string> strList)
            {
                sb.Append('[');
                for (int i = 0; i < strList.Count; i++)
                {
                    if (i > 0) sb.Append(',');
                    sb.Append('"').Append(EscapeJson(strList[i])).Append('"');
                }
                sb.Append(']');
                return;
            }
            // Fallback
            sb.Append('"').Append(EscapeJson(value.ToString())).Append('"');
        }

        private static void AppendString(StringBuilder sb, string key, string value)
        {
            sb.Append('"').Append(key).Append("\":\"").Append(EscapeJson(value ?? "")).Append('"');
        }

        private static void AppendNumber(StringBuilder sb, string key, float value)
        {
            sb.Append('"').Append(key).Append("\":").Append(value.ToString("F2"));
        }

        private static void AppendNumber(StringBuilder sb, string key, int value)
        {
            sb.Append('"').Append(key).Append("\":").Append(value);
        }

        private static string EscapeJson(string s)
        {
            if (string.IsNullOrEmpty(s)) return "";
            return s.Replace("\\", "\\\\").Replace("\"", "\\\"").Replace("\n", "\\n").Replace("\r", "\\r").Replace("\t", "\\t");
        }
    }
}
