using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEngine;

namespace {root-namespace}.Tools.BatchMode.UnityOps.Handlers
{
    /// <summary>
    /// Handles prefab-related commands: create-prefab, edit-prefab, list-prefabs,
    /// and prefab component operations (add/remove/modify/list/inspect).
    /// </summary>
    public class PrefabHandler : IUnityOpsHandler
    {
        public OpsResult Execute(OpsCommandEnvelope cmd)
        {
            switch (cmd.Command)
            {
                case "create-prefab": return CreatePrefab(cmd);
                case "edit-prefab": return EditPrefab(cmd);
                case "list-prefabs": return ListPrefabs(cmd);
                case "prefab-add-component": return PrefabAddComponent(cmd);
                case "prefab-remove-component": return PrefabRemoveComponent(cmd);
                case "prefab-modify-component": return PrefabModifyComponent(cmd);
                case "prefab-list-components": return PrefabListComponents(cmd);
                case "prefab-inspect-component": return PrefabInspectComponent(cmd);
                default: return OpsResult.Error(cmd.Id, cmd.Command, $"PrefabHandler: unknown command {cmd.Command}");
            }
        }

        private OpsResult CreatePrefab(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<CreatePrefabParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'path' parameter");

            p.Path = NormalizePath(p.Path);

            if (!p.Path.EndsWith(".prefab", StringComparison.OrdinalIgnoreCase))
                p.Path += ".prefab";

            if (!cmd.Overwrite && AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab already exists: {p.Path}. Use --overwrite to replace.");

            if (p.Root == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'root' parameter");

            EnsureParentFolder(p.Path);

            var go = BuildGameObject(p.Root, null);
            bool success;
            PrefabUtility.SaveAsPrefabAsset(go, p.Path, out success);
            UnityEngine.Object.DestroyImmediate(go);

            if (!success)
                return OpsResult.Error(cmd.Id, cmd.Command, $"Failed to save prefab: {p.Path}");

            AssetDatabase.Refresh();

            return OpsResult.Success(cmd.Id, cmd.Command, new { path = p.Path },
                $"Prefab created: {p.Path}");
        }

        private OpsResult EditPrefab(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<EditPrefabParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'path' parameter");

            p.Path = NormalizePath(p.Path);

            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab not found: {p.Path}");

            var prefabRoot = PrefabUtility.LoadPrefabContents(p.Path);
            int added = 0, removed = 0, modified = 0;

            if (p.Operations != null)
            {
                foreach (var op in p.Operations)
                {
                    switch (op.Action?.ToLowerInvariant())
                    {
                        case "add":
                            if (op.GameObject != null)
                            {
                                var child = BuildGameObject(op.GameObject, null);
                                child.transform.SetParent(prefabRoot.transform, false);
                                added++;
                            }
                            break;

                        case "remove":
                            var toRemove = FindChildByName(prefabRoot.transform, op.Target);
                            if (toRemove != null)
                            {
                                UnityEngine.Object.DestroyImmediate(toRemove.gameObject);
                                removed++;
                            }
                            else
                            {
                                Debug.LogWarning($"[PrefabHandler] Cannot find child to remove: {op.Target}");
                            }
                            break;

                        case "modify":
                            var toModify = op.Target == prefabRoot.name
                                ? prefabRoot.transform
                                : FindChildByName(prefabRoot.transform, op.Target);
                            if (toModify != null && op.GameObject != null)
                            {
                                ApplyModifications(toModify.gameObject, op.GameObject);
                                modified++;
                            }
                            else
                            {
                                Debug.LogWarning($"[PrefabHandler] Cannot find child to modify: {op.Target}");
                            }
                            break;
                    }
                }
            }

            PrefabUtility.SaveAsPrefabAsset(prefabRoot, p.Path);
            PrefabUtility.UnloadPrefabContents(prefabRoot);

            return OpsResult.Success(cmd.Id, cmd.Command,
                new { path = p.Path, added, removed, modified },
                $"Prefab edited: +{added} -{removed} ~{modified}");
        }

        private OpsResult ListPrefabs(OpsCommandEnvelope cmd)
        {
            var filterPath = cmd.Params?.Value<string>("path");
            var guids = AssetDatabase.FindAssets("t:Prefab");
            var paths = new List<string>();

            foreach (var guid in guids)
            {
                var path = AssetDatabase.GUIDToAssetPath(guid);
                if (string.IsNullOrEmpty(filterPath) || path.StartsWith(NormalizePath(filterPath)))
                    paths.Add(path);
            }
            paths.Sort();

            return OpsResult.Success(cmd.Id, cmd.Command, new { count = paths.Count, prefabs = paths });
        }

        private OpsResult PrefabAddComponent(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<AddComponentParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'path' parameter.");
            if (p.Target == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'target' parameter.");
            if (p.Components == null || p.Components.Count == 0)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'components' parameter.");

            p.Path = NormalizePath(p.Path);
            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab not found: {p.Path}");

            var prefabRoot = PrefabUtility.LoadPrefabContents(p.Path);
            try
            {
                var target = FindTargetInPrefab(prefabRoot, p.Target);
                var added = new List<string>();
                foreach (var comp in p.Components)
                {
                    var type = ResolveComponentType(comp.Type);
                    if (type != null)
                    {
                        var c = target.AddComponent(type);
                        added.Add(c.GetType().Name);
                    }
                }

                PrefabUtility.SaveAsPrefabAsset(prefabRoot, p.Path);
                return OpsResult.Success(cmd.Id, cmd.Command,
                    new { path = p.Path, target = target.name, added },
                    $"Added {added.Count} component(s) to '{target.name}'");
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }
        }

        private OpsResult PrefabRemoveComponent(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<RemoveComponentParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'path' parameter.");
            if (p.Target == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'target' parameter.");
            if (string.IsNullOrEmpty(p.ComponentType))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'componentType' parameter.");

            p.Path = NormalizePath(p.Path);
            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab not found: {p.Path}");

            var prefabRoot = PrefabUtility.LoadPrefabContents(p.Path);
            try
            {
                var target = FindTargetInPrefab(prefabRoot, p.Target);
                var type = ResolveComponentType(p.ComponentType);
                var components = target.GetComponents(type);

                if (components.Length == 0)
                {
                    var existing = GetComponentTypeNames(target);
                    return OpsResult.Error(cmd.Id, cmd.Command,
                        $"Component '{p.ComponentType}' not found on '{target.name}'. Existing components: {existing}");
                }

                int removedCount = 0;
                if (p.Index == -1)
                {
                    for (int i = components.Length - 1; i >= 0; i--)
                    {
                        UnityEngine.Object.DestroyImmediate(components[i]);
                        removedCount++;
                    }
                }
                else
                {
                    if (p.Index < 0 || p.Index >= components.Length)
                        return OpsResult.Error(cmd.Id, cmd.Command,
                            $"Component '{p.ComponentType}' index {p.Index} out of range. Found {components.Length} instance(s).");
                    UnityEngine.Object.DestroyImmediate(components[p.Index]);
                    removedCount = 1;
                }

                PrefabUtility.SaveAsPrefabAsset(prefabRoot, p.Path);
                return OpsResult.Success(cmd.Id, cmd.Command,
                    new { path = p.Path, target = target.name, componentType = p.ComponentType, removedCount },
                    $"Removed {removedCount} '{p.ComponentType}' from '{target.name}'");
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }
        }

        private OpsResult PrefabModifyComponent(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<ModifyComponentParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'path' parameter.");
            if (p.Target == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'target' parameter.");
            if (string.IsNullOrEmpty(p.ComponentType))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'componentType' parameter.");
            if (p.Properties == null || p.Properties.Count == 0)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'properties' parameter.");

            p.Path = NormalizePath(p.Path);
            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab not found: {p.Path}");

            var prefabRoot = PrefabUtility.LoadPrefabContents(p.Path);
            try
            {
                var target = FindTargetInPrefab(prefabRoot, p.Target);
                var type = ResolveComponentType(p.ComponentType);
                var components = target.GetComponents(type);

                if (components.Length == 0)
                {
                    var existing = GetComponentTypeNames(target);
                    return OpsResult.Error(cmd.Id, cmd.Command,
                        $"Component '{p.ComponentType}' not found on '{target.name}'. Existing components: {existing}");
                }

                if (p.Index < 0 || p.Index >= components.Length)
                    return OpsResult.Error(cmd.Id, cmd.Command,
                        $"Component '{p.ComponentType}' index {p.Index} out of range. Found {components.Length} instance(s).");

                SetComponentProperties(components[p.Index], p.Properties);
                PrefabUtility.SaveAsPrefabAsset(prefabRoot, p.Path);

                return OpsResult.Success(cmd.Id, cmd.Command,
                    new { path = p.Path, target = target.name, componentType = p.ComponentType, modifiedProperties = p.Properties.Count },
                    $"Modified {p.Properties.Count} properties on '{p.ComponentType}' of '{target.name}'");
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }
        }

        private OpsResult PrefabListComponents(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<ComponentOperationParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'path' parameter.");
            if (p.Target == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'target' parameter.");

            p.Path = NormalizePath(p.Path);
            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab not found: {p.Path}");

            var prefabRoot = PrefabUtility.LoadPrefabContents(p.Path);
            try
            {
                var target = FindTargetInPrefab(prefabRoot, p.Target);
                var result = BuildComponentList(target);

                return OpsResult.Success(cmd.Id, cmd.Command,
                    new { gameObject = target.name, components = result });
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }
        }

        private OpsResult PrefabInspectComponent(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<InspectComponentParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'path' parameter.");
            if (p.Target == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'target' parameter.");
            if (string.IsNullOrEmpty(p.ComponentType))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'componentType' parameter.");

            p.Path = NormalizePath(p.Path);
            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Prefab not found: {p.Path}");

            var prefabRoot = PrefabUtility.LoadPrefabContents(p.Path);
            try
            {
                var target = FindTargetInPrefab(prefabRoot, p.Target);
                var type = ResolveComponentType(p.ComponentType);
                var components = target.GetComponents(type);

                if (components.Length == 0)
                {
                    var existing = GetComponentTypeNames(target);
                    return OpsResult.Error(cmd.Id, cmd.Command,
                        $"Component '{p.ComponentType}' not found on '{target.name}'. Existing components: {existing}");
                }

                if (p.Index < 0 || p.Index >= components.Length)
                    return OpsResult.Error(cmd.Id, cmd.Command,
                        $"Component '{p.ComponentType}' index {p.Index} out of range. Found {components.Length} instance(s).");

                var so = new SerializedObject(components[p.Index]);
                var propResults = new List<object>();
                var iter = so.GetIterator();
                if (iter.NextVisible(true))
                {
                    do
                    {
                        propResults.Add(new
                        {
                            name = iter.name,
                            type = iter.propertyType.ToString(),
                            value = GetSerializedPropertyValue(iter)
                        });
                    } while (iter.NextVisible(false));
                }

                return OpsResult.Success(cmd.Id, cmd.Command, new
                {
                    type = type.Name,
                    fullType = type.FullName,
                    properties = propResults
                });
            }
            finally
            {
                PrefabUtility.UnloadPrefabContents(prefabRoot);
            }
        }

        // --- Helper methods ---

        private static GameObject BuildGameObject(GameObjectDesc desc, Transform parent)
        {
            var go = new GameObject(desc.Name ?? "GameObject");

            if (!string.IsNullOrEmpty(desc.Tag) && desc.Tag != "Untagged")
                go.tag = desc.Tag;

            if (!string.IsNullOrEmpty(desc.Layer) && desc.Layer != "Default")
                go.layer = LayerMask.NameToLayer(desc.Layer);

            go.SetActive(desc.Active);

            if (parent != null)
                go.transform.SetParent(parent, false);

            if (desc.Transform != null)
            {
                if (desc.Transform.Position != null && desc.Transform.Position.Length >= 3)
                    go.transform.localPosition = new Vector3(desc.Transform.Position[0], desc.Transform.Position[1], desc.Transform.Position[2]);
                if (desc.Transform.Rotation != null && desc.Transform.Rotation.Length >= 3)
                    go.transform.localEulerAngles = new Vector3(desc.Transform.Rotation[0], desc.Transform.Rotation[1], desc.Transform.Rotation[2]);
                if (desc.Transform.Scale != null && desc.Transform.Scale.Length >= 3)
                    go.transform.localScale = new Vector3(desc.Transform.Scale[0], desc.Transform.Scale[1], desc.Transform.Scale[2]);
            }

            if (desc.Components != null)
            {
                foreach (var comp in desc.Components)
                {
                    var type = ResolveComponentType(comp.Type);
                    if (type != null)
                        go.AddComponent(type);
                }
            }

            if (desc.Children != null)
            {
                foreach (var childDesc in desc.Children)
                    BuildGameObject(childDesc, go.transform);
            }

            return go;
        }

        private static GameObject FindTargetInPrefab(GameObject prefabRoot, string target)
        {
            if (string.IsNullOrEmpty(target) || target == prefabRoot.name)
                return prefabRoot;

            var found = FindChildByName(prefabRoot.transform, target);
            if (found != null)
                return found.gameObject;

            throw new ArgumentException($"Target '{target}' not found in prefab. Root: {prefabRoot.name}");
        }

        private static void ApplyModifications(GameObject go, GameObjectDesc desc)
        {
            if (!string.IsNullOrEmpty(desc.Name))
                go.name = desc.Name;

            if (!string.IsNullOrEmpty(desc.Tag) && desc.Tag != "Untagged")
                go.tag = desc.Tag;

            go.SetActive(desc.Active);

            if (desc.Transform != null)
            {
                if (desc.Transform.Position != null && desc.Transform.Position.Length >= 3)
                    go.transform.localPosition = new Vector3(desc.Transform.Position[0], desc.Transform.Position[1], desc.Transform.Position[2]);
                if (desc.Transform.Rotation != null && desc.Transform.Rotation.Length >= 3)
                    go.transform.localEulerAngles = new Vector3(desc.Transform.Rotation[0], desc.Transform.Rotation[1], desc.Transform.Rotation[2]);
                if (desc.Transform.Scale != null && desc.Transform.Scale.Length >= 3)
                    go.transform.localScale = new Vector3(desc.Transform.Scale[0], desc.Transform.Scale[1], desc.Transform.Scale[2]);
            }

            if (desc.Components != null)
            {
                foreach (var comp in desc.Components)
                {
                    var type = ResolveComponentType(comp.Type);
                    if (type != null)
                        go.AddComponent(type);
                }
            }
        }

        private static List<object> BuildComponentList(GameObject go)
        {
            var result = new List<object>();
            var components = go.GetComponents<Component>();
            var typeCounts = new Dictionary<string, int>();

            foreach (var c in components)
            {
                if (c == null) continue;
                var typeName = c.GetType().Name;
                if (!typeCounts.TryGetValue(typeName, out var count))
                    count = 0;
                typeCounts[typeName] = count + 1;

                result.Add(new
                {
                    type = typeName,
                    fullType = c.GetType().FullName,
                    index = count
                });
            }
            return result;
        }

        private static string GetComponentTypeNames(GameObject go)
        {
            var names = new List<string>();
            foreach (var c in go.GetComponents<Component>())
            {
                if (c != null) names.Add(c.GetType().Name);
            }
            return names.Count > 0 ? string.Join(", ", names) : "(none)";
        }

        private static void SetComponentProperties(Component component, Dictionary<string, object> properties)
        {
            var so = new SerializedObject(component);
            foreach (var kvp in properties)
            {
                var prop = so.FindProperty(kvp.Key);
                if (prop == null)
                {
                    Debug.LogWarning($"[PrefabHandler] Property '{kvp.Key}' not found on {component.GetType().Name}");
                    continue;
                }
                SetSerializedPropertyValue(prop, kvp.Value);
            }
            so.ApplyModifiedProperties();
        }

        private static void SetSerializedPropertyValue(SerializedProperty prop, object value)
        {
            switch (prop.propertyType)
            {
                case SerializedPropertyType.Integer:
                    prop.intValue = Convert.ToInt32(value);
                    break;
                case SerializedPropertyType.Float:
                    prop.floatValue = Convert.ToSingle(value);
                    break;
                case SerializedPropertyType.Boolean:
                    prop.boolValue = Convert.ToBoolean(value);
                    break;
                case SerializedPropertyType.String:
                    prop.stringValue = value?.ToString() ?? "";
                    break;
            }
        }

        private static object GetSerializedPropertyValue(SerializedProperty prop)
        {
            switch (prop.propertyType)
            {
                case SerializedPropertyType.Integer: return prop.intValue;
                case SerializedPropertyType.Float: return prop.floatValue;
                case SerializedPropertyType.Boolean: return prop.boolValue;
                case SerializedPropertyType.String: return prop.stringValue;
                case SerializedPropertyType.Enum: return prop.enumNames[prop.enumValueIndex];
                default: return prop.propertyType.ToString();
            }
        }

        private static Type ResolveComponentType(string typeName)
        {
            if (string.IsNullOrEmpty(typeName)) return null;

            var type = Type.GetType(typeName);
            if (type != null) return type;

            type = Type.GetType($"UnityEngine.{typeName}, UnityEngine.CoreModule");
            if (type != null) return type;

            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                type = asm.GetType(typeName);
                if (type != null) return type;

                type = asm.GetType($"UnityEngine.{typeName}");
                if (type != null) return type;
            }

            Debug.LogWarning($"[PrefabHandler] Could not resolve component type: {typeName}");
            return null;
        }

        private static Transform FindChildByName(Transform parent, string name)
        {
            if (string.IsNullOrEmpty(name)) return null;

            for (int i = 0; i < parent.childCount; i++)
            {
                var child = parent.GetChild(i);
                if (child.name == name) return child;
                var found = FindChildByName(child, name);
                if (found != null) return found;
            }
            return null;
        }

        private static string NormalizePath(string path) => path.Replace('\\', '/');

        private static bool AssetExists(string path)
        {
            return !string.IsNullOrEmpty(AssetDatabase.AssetPathToGUID(path, AssetPathToGUIDOptions.OnlyExistingAssets));
        }

        private static void EnsureParentFolder(string assetPath)
        {
            var dir = System.IO.Path.GetDirectoryName(assetPath)?.Replace('\\', '/');
            if (string.IsNullOrEmpty(dir) || dir == "Assets") return;

            var parts = dir.Split('/');
            string current = parts[0];
            for (int i = 1; i < parts.Length; i++)
            {
                string next = current + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[i]);
                current = next;
            }
        }
    }
}
