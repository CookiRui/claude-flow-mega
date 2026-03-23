using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;
using UnityEditor;
using UnityEngine;

namespace {root-namespace}.Tools.BatchMode.UnityOps.Handlers
{
    /// <summary>
    /// Handles asset-related commands: create-material, create-folder, list-assets.
    /// </summary>
    public class AssetHandler : IUnityOpsHandler
    {
        public OpsResult Execute(OpsCommandEnvelope cmd)
        {
            switch (cmd.Command)
            {
                case "create-material": return CreateMaterial(cmd);
                case "create-folder": return CreateFolder(cmd);
                case "list-assets": return ListAssets(cmd);
                default: return OpsResult.Error(cmd.Id, cmd.Command, $"AssetHandler: unknown command {cmd.Command}");
            }
        }

        private OpsResult CreateMaterial(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<CreateMaterialParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'path' parameter");

            p.Path = NormalizePath(p.Path);

            if (!p.Path.EndsWith(".mat", StringComparison.OrdinalIgnoreCase))
                p.Path += ".mat";

            if (!cmd.Overwrite && AssetExists(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, $"Material already exists: {p.Path}. Use --overwrite to replace.");

            var shaderName = string.IsNullOrEmpty(p.Shader) ? "Universal Render Pipeline/Lit" : p.Shader;
            var shader = Shader.Find(shaderName);

            // Fallback: try loading via AssetDatabase if Shader.Find fails (common in -nographics)
            if (shader == null)
            {
                var shaderGuids = AssetDatabase.FindAssets("t:Shader " + shaderName.Split('/')[shaderName.Split('/').Length - 1]);
                foreach (var guid in shaderGuids)
                {
                    var s = AssetDatabase.LoadAssetAtPath<Shader>(AssetDatabase.GUIDToAssetPath(guid));
                    if (s != null && s.name == shaderName)
                    {
                        shader = s;
                        break;
                    }
                }
            }

            if (shader == null)
            {
                // Last fallback: use Standard shader
                shader = Shader.Find("Standard");
                if (shader == null)
                    return OpsResult.Error(cmd.Id, cmd.Command, $"Shader not found: {shaderName} (also tried Standard fallback)");

                Debug.LogWarning($"[AssetHandler] Shader '{shaderName}' not found, falling back to Standard");
            }

            EnsureParentFolder(p.Path);

            var material = new Material(shader);

            if (p.Properties != null)
                ApplyMaterialProperties(material, p.Properties);

            if (cmd.Overwrite && AssetExists(p.Path))
                AssetDatabase.DeleteAsset(p.Path);

            AssetDatabase.CreateAsset(material, p.Path);
            AssetDatabase.Refresh();

            return OpsResult.Success(cmd.Id, cmd.Command,
                new { path = p.Path, shader = shader.name },
                $"Material created: {p.Path} (shader: {shader.name})");
        }

        private OpsResult CreateFolder(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params.ToObject<CreateFolderParams>();
            if (string.IsNullOrEmpty(p.Path))
                return OpsResult.Error(cmd.Id, cmd.Command, "Missing 'path' parameter");

            var path = NormalizePath(p.Path);

            if (AssetDatabase.IsValidFolder(path))
            {
                if (!cmd.Overwrite)
                    return OpsResult.Success(cmd.Id, cmd.Command, new { path, alreadyExists = true },
                        $"Folder already exists: {path}");
            }

            var parts = path.Split('/');
            string current = parts[0]; // "Assets"
            for (int i = 1; i < parts.Length; i++)
            {
                string next = current + "/" + parts[i];
                if (!AssetDatabase.IsValidFolder(next))
                    AssetDatabase.CreateFolder(current, parts[i]);
                current = next;
            }

            return OpsResult.Success(cmd.Id, cmd.Command, new { path },
                $"Folder created: {path}");
        }

        private OpsResult ListAssets(OpsCommandEnvelope cmd)
        {
            var p = cmd.Params?.ToObject<ListAssetsParams>() ?? new ListAssetsParams();
            var filterType = p.Type;
            var filterPath = string.IsNullOrEmpty(p.Path) ? null : NormalizePath(p.Path);

            string searchFilter = string.IsNullOrEmpty(filterType) ? "" : $"t:{filterType}";
            string[] searchFolders = string.IsNullOrEmpty(filterPath) ? null : new[] { filterPath };

            string[] guids;
            if (searchFolders != null)
                guids = AssetDatabase.FindAssets(searchFilter, searchFolders);
            else
                guids = AssetDatabase.FindAssets(searchFilter);

            var assets = new List<AssetInfo>();
            foreach (var guid in guids)
            {
                var assetPath = AssetDatabase.GUIDToAssetPath(guid);
                var assetType = AssetDatabase.GetMainAssetTypeAtPath(assetPath);
                assets.Add(new AssetInfo
                {
                    Path = assetPath,
                    Type = assetType?.Name ?? "Unknown"
                });
            }

            assets.Sort((a, b) => string.Compare(a.Path, b.Path, StringComparison.Ordinal));

            return OpsResult.Success(cmd.Id, cmd.Command, new { count = assets.Count, assets });
        }

        private static void ApplyMaterialProperties(Material material, Dictionary<string, object> properties)
        {
            foreach (var kvp in properties)
            {
                try
                {
                    ApplyMaterialProperty(material, kvp.Key, kvp.Value);
                }
                catch (Exception e)
                {
                    Debug.LogWarning($"[AssetHandler] Failed to set material property '{kvp.Key}': {e.Message}");
                }
            }
        }

        private static void ApplyMaterialProperty(Material material, string name, object value)
        {
            if (!material.HasProperty(name))
            {
                Debug.LogWarning($"[AssetHandler] Material does not have property: {name}");
                return;
            }

            if (value is JArray arr)
            {
                if (arr.Count >= 3)
                {
                    float a = arr.Count >= 4 ? arr[3].Value<float>() : 1f;
                    material.SetColor(name, new Color(
                        arr[0].Value<float>(), arr[1].Value<float>(), arr[2].Value<float>(), a));
                    return;
                }
            }

            if (value is JToken jt)
            {
                switch (jt.Type)
                {
                    case JTokenType.Float:
                    case JTokenType.Integer:
                        material.SetFloat(name, jt.Value<float>());
                        return;
                    case JTokenType.String:
                        var texPath = jt.Value<string>();
                        if (texPath.StartsWith("asset:", StringComparison.OrdinalIgnoreCase))
                            texPath = texPath.Substring("asset:".Length);
                        var tex = AssetDatabase.LoadAssetAtPath<Texture>(texPath);
                        if (tex != null)
                            material.SetTexture(name, tex);
                        else
                            Debug.LogWarning($"[AssetHandler] Texture not found: {texPath}");
                        return;
                }
            }

            if (value is double d)
            {
                material.SetFloat(name, (float)d);
                return;
            }
            if (value is long l)
            {
                material.SetFloat(name, l);
                return;
            }
            if (value is string s)
            {
                var tex = AssetDatabase.LoadAssetAtPath<Texture>(s);
                if (tex != null)
                    material.SetTexture(name, tex);
            }
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

        private class AssetInfo
        {
            [JsonProperty("path")] public string Path;
            [JsonProperty("type")] public string Type;
        }
    }
}
