using System;
using System.Collections.Generic;
using System.Reflection;
using UnityEngine;

namespace {root-namespace}.Tools.AutoTest
{
    public static class TypeRegistry
    {
        private static readonly Dictionary<string, Type> _actions = new();
        private static readonly Dictionary<string, Type> _conditions = new();
        private static bool _initialized;

        public static IReadOnlyDictionary<string, Type> Actions
        {
            get { EnsureInitialized(); return _actions; }
        }

        public static IReadOnlyDictionary<string, Type> Conditions
        {
            get { EnsureInitialized(); return _conditions; }
        }

        public static void EnsureInitialized()
        {
            if (_initialized) return;
            _initialized = true;
            ScanAssemblies();
        }

        private static void ScanAssemblies()
        {
            foreach (var assembly in AppDomain.CurrentDomain.GetAssemblies())
            {
                try
                {
                    foreach (var type in assembly.GetTypes())
                    {
                        var actionAttr = type.GetCustomAttribute<AutoTestActionAttribute>();
                        if (actionAttr != null && typeof(TestAction).IsAssignableFrom(type) && !type.IsAbstract)
                        {
                            if (_actions.ContainsKey(actionAttr.TypeName))
                            {
                                Debug.LogWarning($"[AutoTest] Duplicate action type '{actionAttr.TypeName}': {type.FullName} vs {_actions[actionAttr.TypeName].FullName}");
                                continue;
                            }
                            _actions[actionAttr.TypeName] = type;
                        }

                        var condAttr = type.GetCustomAttribute<AutoTestConditionAttribute>();
                        if (condAttr != null && typeof(TestCondition).IsAssignableFrom(type) && !type.IsAbstract)
                        {
                            if (_conditions.ContainsKey(condAttr.TypeName))
                            {
                                Debug.LogWarning($"[AutoTest] Duplicate condition type '{condAttr.TypeName}': {type.FullName} vs {_conditions[condAttr.TypeName].FullName}");
                                continue;
                            }
                            _conditions[condAttr.TypeName] = type;
                        }
                    }
                }
                catch (ReflectionTypeLoadException)
                {
                    // Skip assemblies that fail to load types
                }
            }

            Debug.Log($"[AutoTest] TypeRegistry: {_actions.Count} actions, {_conditions.Count} conditions registered");
        }

        public static TestAction CreateAction(string typeName)
        {
            EnsureInitialized();
            if (!_actions.TryGetValue(typeName, out var type))
                return null;
            return (TestAction)Activator.CreateInstance(type);
        }

        public static TestCondition CreateCondition(string typeName)
        {
            EnsureInitialized();
            if (!_conditions.TryGetValue(typeName, out var type))
                return null;
            return (TestCondition)Activator.CreateInstance(type);
        }
    }
}
