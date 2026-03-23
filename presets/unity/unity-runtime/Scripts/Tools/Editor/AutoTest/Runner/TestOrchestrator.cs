using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;
using Debug = UnityEngine.Debug;

namespace {root-namespace}.Tools.AutoTest
{
    public class TestOrchestrator
    {
        public async Task<TestResultData> Execute(TestCase testCase, CancellationToken ct)
        {
            var result = new TestResultData
            {
                Id = testCase.Id + "_" + DateTime.Now.ToString("yyyyMMdd_HHmmss_fff"),
                TestName = testCase.Name,
                Scene = testCase.Scene,
                Timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss")
            };

            var overallStart = Time.realtimeSinceStartup;
            using var logCapture = new LogCapture();
            var runner = new AutoTestRunner(logCapture);

            // Create a timeout CTS linked to the parent
            using var timeoutCts = CancellationTokenSource.CreateLinkedTokenSource(ct);
            timeoutCts.CancelAfter(TimeSpan.FromSeconds(testCase.MaxDuration));
            var token = timeoutCts.Token;

            try
            {
                // === Setup Phase ===
                if (testCase.Setup != null && testCase.Setup.Length > 0)
                {
                    Debug.Log("[AutoTest] === Setup Phase ===");
                    var setupStart = Time.realtimeSinceStartup;
                    var setupResults = await runner.RunSteps(testCase.Setup, token);
                    result.SetupPhase = new PhaseResult
                    {
                        Duration = Time.realtimeSinceStartup - setupStart,
                        Steps = setupResults
                    };

                    // Check if setup failed with Abort
                    bool setupFailed = false;
                    foreach (var sr in setupResults)
                    {
                        if (sr.Result == StepResult.Failed || sr.Result == StepResult.Timeout)
                        {
                            setupFailed = true;
                            break;
                        }
                    }

                    if (setupFailed)
                    {
                        result.SetupPhase.Status = "failed";
                        result.Status = "failed";
                        result.Duration = Time.realtimeSinceStartup - overallStart;
                        result.CapturedErrors = logCapture.GetErrors();
                        Debug.LogError("[AutoTest] Setup phase failed, aborting test");
                        return result;
                    }
                    result.SetupPhase.Status = "passed";
                }

                // === Test Phase ===
                Debug.Log("[AutoTest] === Test Phase ===");
                var testStart = Time.realtimeSinceStartup;
                logCapture.Clear(); // Clear setup errors for test phase
                var testResults = await runner.RunSteps(testCase.Steps, token);
                result.TestSteps = testResults;

                // === Cleanup Phase ===
                if (testCase.Cleanup != null && testCase.Cleanup.Length > 0)
                {
                    Debug.Log("[AutoTest] === Cleanup Phase ===");
                    var cleanupStart = Time.realtimeSinceStartup;
                    // Cleanup uses parent ct, not timeout ct — cleanup should try to complete
                    var cleanupResults = await runner.RunSteps(testCase.Cleanup, ct);
                    result.CleanupPhase = new PhaseResult
                    {
                        Duration = Time.realtimeSinceStartup - cleanupStart,
                        Steps = cleanupResults,
                        Status = "passed" // Cleanup failures are just warnings
                    };
                }
            }
            catch (OperationCanceledException)
            {
                if (timeoutCts.IsCancellationRequested && !ct.IsCancellationRequested)
                {
                    result.Status = "timeout";
                    Debug.LogError($"[AutoTest] Test exceeded maxDuration of {testCase.MaxDuration}s");
                }
                else
                {
                    result.Status = "cancelled";
                    Debug.LogWarning("[AutoTest] Test was cancelled");
                }
            }
            catch (Exception e)
            {
                result.Status = "error";
                Debug.LogError($"[AutoTest] Unexpected error: {e}");
            }

            // Compute summary
            result.Duration = Time.realtimeSinceStartup - overallStart;
            result.CapturedErrors = logCapture.GetErrors();

            if (string.IsNullOrEmpty(result.Status))
                result.Status = ComputeStatus(result.TestSteps);

            Debug.Log($"[AutoTest] Test '{testCase.Name}' completed: {result.Status} ({result.Duration:F2}s)");
            return result;
        }

        private static string ComputeStatus(List<AutoTestRunner.StepResultData> steps)
        {
            if (steps == null) return "error";
            bool anyFailed = false;
            bool anyTimeout = false;
            foreach (var s in steps)
            {
                if (s.Result == StepResult.Failed) anyFailed = true;
                if (s.Result == StepResult.Timeout) anyTimeout = true;
            }
            if (anyFailed) return "failed";
            if (anyTimeout) return "timeout";
            return "passed";
        }
    }

    public class TestResultData
    {
        public string Id;
        public string TestName;
        public string Scene;
        public string Status;
        public string Timestamp;
        public float Duration;
        public PhaseResult SetupPhase;
        public List<AutoTestRunner.StepResultData> TestSteps;
        public PhaseResult CleanupPhase;
        public List<LogCapture.LogEntry> CapturedErrors;
    }

    public class PhaseResult
    {
        public string Status;
        public float Duration;
        public List<AutoTestRunner.StepResultData> Steps;
    }
}
