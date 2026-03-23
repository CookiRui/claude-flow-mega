using System;
using System.Collections.Generic;
using UnityEditor;
using UnityEditor.SceneManagement;
using UnityEngine;
using UnityEngine.SceneManagement;

namespace {root-namespace}.Tools.BatchMode.UnityOps.Handlers
{
    /// <summary>
    /// Handles scene-related commands: create-scene, edit-scene, list-scenes,
    /// and scene component operations (add/remove/modify/list/inspect).
    /// </summary>
    public class SceneHandler : IUnityOpsHandler
    {
        public OpsResult Execute(OpsCommandEnvelope cmd)
        {
            switch (cmd.Command)
            {
                case "create-scene": return CreateScene(cmd);
                case "edit-scene": return EditScene(cmd);
                case "list-scenes": return ListScenes(cmd);
                case "scene-add-component": return SceneAddComponent(cmd);
                case "scene-remove-component": return SceneRemoveComponent(cmd);
                case "scene-modify-component": return SceneModifyComponent(cmd);
                case "scene-list-components": return SceneListComponents(cmd);
                case "scene-inspect-component": return SceneInspectComponent(cmd);
                default: return OpsResult.Error(cmd.Id, cmd.Command, $"SceneHandler: unknown command {cmd.Command}");
            }
        }

        private OpsResult CreateScene(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<CreateSceneParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'path' parameter");

            p.Path = NormalizePath(p.Path);

            if (!p.Path.EndsWith(".unity", StringComparison.OrdinalIgnoreCase))
                p.Path += ".unity";

            if (!cmd.Overwrite && AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene already exists: {p.Path}. Use --overwrite to replace.");

            EnsureParentFolder(p.Path);

            var scene = EditorSceneManager.NewScene(NewSceneSetup.EmptyScene, NewSceneMode.Single);

            int goCount = 0;
            if (p.GameObjects != null)
            {
                foreach (var desc in p.GameObjects)
                {
                    BuildGameObject(desc, null);
                    goCount++;
                }
            }

            EditorSceneManager.SaveScene(scene, p.Path);

            if (p.AddToBuildSettings)
                AddSceneToBuildSettings(p.Path);

            AssetDatabase.Refresh();

            return OpsResult.Success(cmd.Id, cmd.Command, new { path = p.Path, gameObjectCount = goCount },
                $"Scene created: {p.Path}");
        }

        private OpsResult EditScene(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<EditSceneParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'path' parameter");

            p.Path = NormalizePath(p.Path);

            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene not found: {p.Path}");

            var scene = EditorSceneManager.OpenScene(p.Path, OpenSceneMode.Single);
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
                                BuildGameObject(op.GameObject, null);
                                added++;
                            }
                            break;

                        case "remove":
                            var toRemove = GameObject.Find(op.Target);
                            if (toRemove != null)
                            {
                                UnityEngine.Object.DestroyImmediate(toRemove);
                                removed++;
                            }
                            else
                            {
                                Debug.LogWarning($"[SceneHandler] Cannot find GO to remove: {op.Target}");
                            }
                            break;

                        case "modify":
                            var toModify = GameObject.Find(op.Target);
                            if (toModify != null && op.GameObject != null)
                            {
                                ApplyModifications(toModify, op.GameObject);
                                modified++;
                            }
                            else
                            {
                                Debug.LogWarning($"[SceneHandler] Cannot find GO to modify: {op.Target}");
                            }
                            break;

                        default:
                            Debug.LogWarning($"[SceneHandler] Unknown operation: {op.Action}");
                            break;
                    }
                }
            }

            EditorSceneManager.SaveScene(scene);

            return OpsResult.Success(cmd.Id, cmd.Command,
                new { path = p.Path, added, removed, modified },
                $"Scene edited: +{added} -{removed} ~{modified}");
        }

        private OpsResult ListScenes(OpsCommandEnvelope cmd)
        {
            var guids = AssetDatabase.FindAssets("t:SceneAsset");
            var paths = new List<string>();
            foreach (var guid in guids)
                paths.Add(AssetDatabase.GUIDToAssetPath(guid));
            paths.Sort();

            return OpsResult.Success(cmd.Id, cmd.Command, new { count = paths.Count, scenes = paths });
        }

        private OpsResult SceneAddComponent(OpsCommandEnvelope cmd)
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
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene not found: {p.Path}");

            var scene = EditorSceneManager.OpenScene(p.Path, OpenSceneMode.Single);
            var go = FindSceneGameObject(p.Target);

            var added = new List<string>();
            foreach (var comp in p.Components)
            {
                var type = ResolveComponentType(comp.Type);
                if (type != null)
                {
                    var c = go.AddComponent(type);
                    added.Add(c.GetType().Name);
                }
            }

            EditorSceneManager.SaveScene(scene);
            return OpsResult.Success(cmd.Id, cmd.Command,
                new { path = p.Path, target = go.name, added },
                $"Added {added.Count} component(s) to '{go.name}'");
        }

        private OpsResult SceneRemoveComponent(OpsCommandEnvelope cmd)
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
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene not found: {p.Path}");

            var scene = EditorSceneManager.OpenScene(p.Path, OpenSceneMode.Single);
            var go = FindSceneGameObject(p.Target);

            var type = ResolveComponentType(p.ComponentType);
            var components = go.GetComponents(type);

            if (components.Length == 0)
            {
                var existing = GetComponentTypeNames(go);
                return OpsResult.Error(cmd.Id, cmd.Command,
                    $"Component '{p.ComponentType}' not found on '{go.name}'. Existing components: {existing}");
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

            EditorSceneManager.SaveScene(scene);
            return OpsResult.Success(cmd.Id, cmd.Command,
                new { path = p.Path, target = go.name, componentType = p.ComponentType, removedCount },
                $"Removed {removedCount} '{p.ComponentType}' from '{go.name}'");
        }

        private OpsResult SceneModifyComponent(OpsCommandEnvelope cmd)
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
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene not found: {p.Path}");

            var scene = EditorSceneManager.OpenScene(p.Path, OpenSceneMode.Single);
            var go = FindSceneGameObject(p.Target);

            var type = ResolveComponentType(p.ComponentType);
            var components = go.GetComponents(type);

            if (components.Length == 0)
            {
                var existing = GetComponentTypeNames(go);
                return OpsResult.Error(cmd.Id, cmd.Command,
                    $"Component '{p.ComponentType}' not found on '{go.name}'. Existing components: {existing}");
            }

            if (p.Index < 0 || p.Index >= components.Length)
                return OpsResult.Error(cmd.Id, cmd.Command,
                    $"Component '{p.ComponentType}' index {p.Index} out of range. Found {components.Length} instance(s).");

            SetComponentProperties(components[p.Index], p.Properties);
            EditorSceneManager.SaveScene(scene);

            return OpsResult.Success(cmd.Id, cmd.Command,
                new { path = p.Path, target = go.name, componentType = p.ComponentType, modifiedProperties = p.Properties.Count },
                $"Modified {p.Properties.Count} properties on '{p.ComponentType}' of '{go.name}'");
        }

        private OpsResult SceneListComponents(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<ComponentOperationParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'path' parameter.");
            if (p.Target == null)
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing required 'target' parameter.");

            p.Path = NormalizePath(p.Path);
            if (!AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene not found: {p.Path}");

            EditorSceneManager.OpenScene(p.Path, OpenSceneMode.Single);
            var go = FindSceneGameObject(p.Target);

            var result = BuildComponentList(go);
            return OpsResult.Success(cmd.Id, cmd.Command,
                new { gameObject = go.name, components = result });
        }

        private OpsResult SceneInspectComponent(OpsCommandEnvelope cmd)
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
                return OpsResult.Error(cmd.Id, cmd.Command, $"Scene not found: {p.Path}");

            EditorSceneManager.OpenScene(p.Path, OpenSceneMode.Single);
            var go = FindSceneGameObject(p.Target);

            var type = ResolveComponentType(p.ComponentType);
            var components = go.GetComponents(type);

            if (components.Length == 0)
            {
                var existing = GetComponentTypeNames(go);
                return OpsResult.Error(cmd.Id, cmd.Command,
                    $"Component '{p.ComponentType}' not found on '{go.name}'. Existing components: {existing}");
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

        private static GameObject FindSceneGameObject(string target)
        {
            if (string.IsNullOrEmpty(target))
                throw new ArgumentException("Target GameObject name is required for scene operations.");

            var rootName = target.Contains("/") ? target.Split('/')[0] : target;

            var scene = SceneManager.GetActiveScene();
            foreach (var rootGo in scene.GetRootGameObjects())
            {
                if (rootGo.name == rootName)
                    return rootGo;
            }

            var names = new List<string>();
            foreach (var rootGo in scene.GetRootGameObjects())
                names.Add(rootGo.name);

            throw new ArgumentException(
                $"GameObject '{rootName}' not found in scene. Root objects: {string.Join(", ", names)}");
        }

        private static void ApplyModifications(GameObject go, GameObjectDesc desc)
        {
            if (!string.IsNullOrEmpty(desc.Name))
                go.name = desc.Name;

            if (!string.IsNullOrEmpty(desc.Tag) && desc.Tag != "Untagged")
                go.tag = desc.Tag;

            if (!string.IsNullOrEmpty(desc.Layer) && desc.Layer != "Default")
                go.layer = LayerMask.NameToLayer(desc.Layer);

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

            if (desc.Children != null)
            {
                foreach (var childDesc in desc.Children)
                    BuildGameObject(childDesc, go.transform);
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
                    Debug.LogWarning($"[SceneHandler] Property '{kvp.Key}' not found on {component.GetType().Name}");
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

            // Try direct resolve
            var type = Type.GetType(typeName);
            if (type != null) return type;

            // Try UnityEngine namespace
            type = Type.GetType($"UnityEngine.{typeName}, UnityEngine.CoreModule");
            if (type != null) return type;

            // Search all loaded assemblies
            foreach (var asm in AppDomain.CurrentDomain.GetAssemblies())
            {
                type = asm.GetType(typeName);
                if (type != null) return type;

                type = asm.GetType($"UnityEngine.{typeName}");
                if (type != null) return type;
            }

            Debug.LogWarning($"[SceneHandler] Could not resolve component type: {typeName}");
            return null;
        }

        private static void AddSceneToBuildSettings(string scenePath)
        {
            var scenes = new List<EditorBuildSettingsScene>(EditorBuildSettings.scenes);
            foreach (var s in scenes)
            {
                if (s.path == scenePath) return;
            }
            scenes.Add(new EditorBuildSettingsScene(scenePath, true));
            EditorBuildSettings.scenes = scenes.ToArray();
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
            string current = parts[0]; // "Assets"
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
