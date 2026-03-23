using System;
using System.Collections.Generic;
using Newtonsoft.Json.Linq;
using UnityEngine;

namespace {root-namespace}.Tools.AutoTest
{
    public static class JsonTestCaseParser
    {
        public static TestCase Parse(string json, Dictionary<string, string> cliVars = null)
        {
            var root = JObject.Parse(json);
            var testCase = new TestCase();

            testCase.Id = root.Value<string>("id") ?? "unnamed_test";
            testCase.Scene = root.Value<string>("scene");

            // Merge parameters: JSON parameters as base, CLI vars override
            var parameters = new Dictionary<string, string>();
            var jsonParams = root["parameters"] as JObject;
            if (jsonParams != null)
            {
                foreach (var kvp in jsonParams)
                    parameters[kvp.Key] = kvp.Value.ToString();
            }
            if (cliVars != null)
            {
                foreach (var kvp in cliVars)
                    parameters[kvp.Key] = kvp.Value;
            }
            testCase.Parameters = parameters;

            var test = root["test"] as JObject;
            if (test == null)
            {
                Debug.LogError("[AutoTest] JSON missing 'test' object");
                return null;
            }

            testCase.Name = test.Value<string>("name") ?? testCase.Id;
            testCase.Description = test.Value<string>("description") ?? "";
            testCase.MaxDuration = test.Value<float?>("maxDuration") ?? 120f;

            // Parse phases
            testCase.Setup = ParseSteps(test["setup"] as JArray, parameters);
            testCase.Steps = ParseSteps(test["steps"] as JArray, parameters);
            testCase.Cleanup = ParseSteps(test["cleanup"] as JArray, parameters);

            if (testCase.Steps == null || testCase.Steps.Length == 0)
            {
                Debug.LogError("[AutoTest] JSON 'test.steps' is empty or missing");
                return null;
            }

            return testCase;
        }

        private static TestStep[] ParseSteps(JArray stepsArray, Dictionary<string, string> parameters)
        {
            if (stepsArray == null) return null;

            var steps = new List<TestStep>();
            foreach (var stepJson in stepsArray)
            {
                var step = ParseStep(stepJson as JObject, parameters);
                if (step != null)
                    steps.Add(step);
            }
            return steps.Count > 0 ? steps.ToArray() : null;
        }

        private static TestStep ParseStep(JObject stepJson, Dictionary<string, string> parameters)
        {
            if (stepJson == null) return null;

            var step = new TestStep();
            step.Name = stepJson.Value<string>("name") ?? "unnamed_step";
            step.WaitAfterAction = stepJson.Value<float?>("waitAfterAction") ?? 0.5f;
            step.Timeout = stepJson.Value<float?>("timeout") ?? 5f;
            step.PollingInterval = stepJson.Value<float?>("pollingInterval") ?? 0.1f;
            step.RetryCount = stepJson.Value<int?>("retryCount") ?? 0;
            step.RetryDelay = stepJson.Value<float?>("retryDelay") ?? 1f;

            var failPolicy = stepJson.Value<string>("failPolicy");
            if (failPolicy == "Abort")
                step.FailPolicy = FailPolicy.Abort;

            // Parse action
            var actionJson = stepJson["action"] as JObject;
            if (actionJson != null)
            {
                step.Action = ParseAction(actionJson, parameters);
            }

            // Parse pre/post conditions
            var preCond = stepJson["preCondition"] as JObject;
            if (preCond != null)
                step.PreCondition = ParseCondition(preCond, parameters);

            var postCond = stepJson["postCondition"] as JObject;
            if (postCond != null)
                step.PostCondition = ParseCondition(postCond, parameters);

            // Parse captureContext
            var capture = stepJson["captureContext"] as JArray;
            if (capture != null)
            {
                var items = new List<string>();
                foreach (var item in capture)
                    items.Add(item.ToString());
                step.CaptureContext = items.ToArray();
            }

            return step;
        }

        private static TestAction ParseAction(JObject actionJson, Dictionary<string, string> parameters)
        {
            var typeName = actionJson.Value<string>("type");
            if (string.IsNullOrEmpty(typeName))
            {
                Debug.LogError("[AutoTest] Action missing 'type' field");
                return null;
            }

            var action = TypeRegistry.CreateAction(typeName);
            if (action == null)
            {
                Debug.LogError($"[AutoTest] Unknown action type: '{typeName}'");
                return null;
            }

            // Convert JObject to Dictionary for Configure
            var dict = new Dictionary<string, object>();
            foreach (var kvp in actionJson)
            {
                if (kvp.Key == "type") continue;
                dict[kvp.Key] = ConvertJToken(kvp.Value, parameters);
            }
            action.Configure(dict);

            return action;
        }

        private static TestCondition ParseCondition(JObject condJson, Dictionary<string, string> parameters)
        {
            var typeName = condJson.Value<string>("type");
            if (string.IsNullOrEmpty(typeName))
            {
                Debug.LogError("[AutoTest] Condition missing 'type' field");
                return null;
            }

            var condition = TypeRegistry.CreateCondition(typeName);
            if (condition == null)
            {
                Debug.LogError($"[AutoTest] Unknown condition type: '{typeName}'");
                return null;
            }

            var dict = new Dictionary<string, object>();
            foreach (var kvp in condJson)
            {
                if (kvp.Key == "type") continue;
                dict[kvp.Key] = ConvertJToken(kvp.Value, parameters);
            }
            condition.Configure(dict);

            return condition;
        }

        private static object ConvertJToken(JToken token, Dictionary<string, string> parameters)
        {
            switch (token.Type)
            {
                case JTokenType.String:
                    return SubstituteParameters(token.Value<string>(), parameters);
                case JTokenType.Integer:
                    return token.Value<long>();
                case JTokenType.Float:
                    return token.Value<double>();
                case JTokenType.Boolean:
                    return token.Value<bool>();
                case JTokenType.Array:
                    var list = new List<object>();
                    foreach (var item in token)
                        list.Add(ConvertJToken(item, parameters));
                    return list;
                case JTokenType.Object:
                    var dict = new Dictionary<string, object>();
                    foreach (var kvp in (JObject)token)
                        dict[kvp.Key] = ConvertJToken(kvp.Value, parameters);
                    return dict;
                default:
                    return token.ToString();
            }
        }

        private static string SubstituteParameters(string value, Dictionary<string, string> parameters)
        {
            if (parameters == null || string.IsNullOrEmpty(value)) return value;
            foreach (var kvp in parameters)
            {
                value = value.Replace("{{" + kvp.Key + "}}", kvp.Value);
            }
            return value;
        }
    }
}
