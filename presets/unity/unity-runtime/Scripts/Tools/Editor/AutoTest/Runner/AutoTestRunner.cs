using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using UnityEngine;

namespace {root-namespace}.Tools.AutoTest
{
    public class AutoTestRunner
    {
        public struct StepResultData
        {
            public int Index;
            public string Name;
            public StepResult Result;
            public float Duration;
            public string Message;
            public Dictionary<string, object> Context;
        }

        private readonly LogCapture _logCapture;

        public AutoTestRunner(LogCapture logCapture)
        {
            _logCapture = logCapture;
        }

        public async Task<List<StepResultData>> RunSteps(TestStep[] steps, CancellationToken ct)
        {
            var results = new List<StepResultData>();
            if (steps == null) return results;

            for (int i = 0; i < steps.Length; i++)
            {
                ct.ThrowIfCancellationRequested();
                var step = steps[i];
                var result = await RunSingleStep(i, step, ct);
                results.Add(result);

                if (result.Result != StepResult.Passed && result.Result != StepResult.Skipped
                    && step.FailPolicy == FailPolicy.Abort)
                {
                    Debug.Log($"[AutoTest] Step {i} '{step.Name}' failed with Abort policy, stopping.");
                    break;
                }
            }

            return results;
        }

        private async Task<StepResultData> RunSingleStep(int index, TestStep step, CancellationToken ct)
        {
            var startTime = Time.realtimeSinceStartup;
            Debug.Log($"[AutoTest] Step {index}: '{step.Name}' — starting");

            // 1. Check PreCondition
            if (step.PreCondition != null && !step.PreCondition.Check())
            {
                Debug.Log($"[AutoTest] Step {index}: '{step.Name}' — skipped (precondition not met: {step.PreCondition.FailMessage})");
                return new StepResultData
                {
                    Index = index,
                    Name = step.Name,
                    Result = StepResult.Skipped,
                    Duration = Time.realtimeSinceStartup - startTime,
                    Message = $"PreCondition not met: {step.PreCondition.FailMessage}"
                };
            }

            // 2. Execute Action (with retry)
            bool actionSuccess = false;
            int attempts = 1 + step.RetryCount;
            string actionError = null;

            if (step.Action != null)
            {
                for (int attempt = 0; attempt < attempts; attempt++)
                {
                    try
                    {
                        actionSuccess = await step.Action.Execute(ct);
                        if (actionSuccess) break;
                        actionError = $"Action returned false (attempt {attempt + 1}/{attempts})";
                    }
                    catch (OperationCanceledException)
                    {
                        throw;
                    }
                    catch (Exception e)
                    {
                        actionError = $"Action threw {e.GetType().Name}: {e.Message}";
                        Debug.LogWarning($"[AutoTest] Step {index}: {actionError}");
                    }

                    if (attempt < attempts - 1)
                    {
                        Debug.Log($"[AutoTest] Step {index}: retrying in {step.RetryDelay}s...");
                        await Task.Delay(TimeSpan.FromSeconds(step.RetryDelay), ct);
                    }
                }

                if (!actionSuccess)
                {
                    return new StepResultData
                    {
                        Index = index,
                        Name = step.Name,
                        Result = StepResult.Failed,
                        Duration = Time.realtimeSinceStartup - startTime,
                        Message = actionError ?? "Action failed"
                    };
                }
            }

            // 3. Wait after action
            if (step.WaitAfterAction > 0)
            {
                await Task.Delay(TimeSpan.FromSeconds(step.WaitAfterAction), ct);
            }

            // 4. Poll PostCondition
            if (step.PostCondition != null)
            {
                var pollStart = Time.realtimeSinceStartup;
                bool conditionMet = false;

                while (Time.realtimeSinceStartup - pollStart < step.Timeout)
                {
                    ct.ThrowIfCancellationRequested();
                    if (step.PostCondition.Check())
                    {
                        conditionMet = true;
                        break;
                    }
                    await Task.Delay(TimeSpan.FromSeconds(step.PollingInterval), ct);
                }

                if (!conditionMet)
                {
                    return new StepResultData
                    {
                        Index = index,
                        Name = step.Name,
                        Result = StepResult.Timeout,
                        Duration = Time.realtimeSinceStartup - startTime,
                        Message = $"Timeout: {step.PostCondition.FailMessage} after {step.Timeout}s"
                    };
                }
            }

            // 5. Check LogCapture for errors
            if (_logCapture != null && _logCapture.HasErrors)
            {
                var errors = _logCapture.GetErrors();
                var lastError = errors[errors.Count - 1];
                return new StepResultData
                {
                    Index = index,
                    Name = step.Name,
                    Result = StepResult.Failed,
                    Duration = Time.realtimeSinceStartup - startTime,
                    Message = $"Unity error captured: {lastError.Type}: {lastError.Message}"
                };
            }

            Debug.Log($"[AutoTest] Step {index}: '{step.Name}' — passed ({Time.realtimeSinceStartup - startTime:F2}s)");
            return new StepResultData
            {
                Index = index,
                Name = step.Name,
                Result = StepResult.Passed,
                Duration = Time.realtimeSinceStartup - startTime,
                Message = "OK"
            };
        }
    }
}
