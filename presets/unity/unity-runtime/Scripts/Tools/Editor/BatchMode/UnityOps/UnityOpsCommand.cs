using System;
using System.Collections.Generic;
using Newtonsoft.Json;
using Newtonsoft.Json.Linq;

namespace {root-namespace}.Tools.BatchMode.UnityOps
{
    [Serializable]
    public class OpsCommandEnvelope
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("command")] public string Command;
        [JsonProperty("overwrite")] public bool Overwrite;
        [JsonProperty("params")] public JObject Params;
    }

    [Serializable]
    public class OpsResult
    {
        [JsonProperty("id")] public string Id;
        [JsonProperty("command")] public string Command;
        [JsonProperty("status")] public string Status;
        [JsonProperty("timestamp")] public string Timestamp;
        [JsonProperty("message")] public string Message;
        [JsonProperty("result")] public object Result;

        public static OpsResult Success(string id, string command, object result = null, string message = null)
        {
            return new OpsResult
            {
                Id = id,
                Command = command,
                Status = "success",
                Timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
                Message = message ?? "OK",
                Result = result
            };
        }

        public static OpsResult Error(string id, string command, string message)
        {
            return new OpsResult
            {
                Id = id,
                Command = command,
                Status = "error",
                Timestamp = DateTime.Now.ToString("yyyy-MM-ddTHH:mm:ss"),
                Message = message
            };
        }
    }

    // --- Param classes for each command ---

    [Serializable]
    public class CreateSceneParams
    {
        [JsonProperty("path")] public string Path;
        [JsonProperty("gameObjects")] public List<GameObjectDesc> GameObjects;
        [JsonProperty("addToBuildSettings")] public bool AddToBuildSettings;
    }

    [Serializable]
    public class EditSceneParams
    {
        [JsonProperty("path")] public string Path;
        [JsonProperty("operations")] public List<SceneOperation> Operations;
    }

    [Serializable]
    public class SceneOperation
    {
        [JsonProperty("action")] public string Action; // add, remove, modify
        [JsonProperty("target")] public string Target; // GO name (for remove/modify)
        [JsonProperty("gameObject")] public GameObjectDesc GameObject; // for add/modify
    }

    [Serializable]
    public class CreatePrefabParams
    {
        [JsonProperty("path")] public string Path;
        [JsonProperty("root")] public GameObjectDesc Root;
    }

    [Serializable]
    public class EditPrefabParams
    {
        [JsonProperty("path")] public string Path;
        [JsonProperty("operations")] public List<SceneOperation> Operations;
    }

    [Serializable]
    public class CreateMaterialParams
    {
        [JsonProperty("path")] public string Path;
        [JsonProperty("shader")] public string Shader;
        [JsonProperty("properties")] public Dictionary<string, object> Properties;
    }

    [Serializable]
    public class CreateFolderParams
    {
        [JsonProperty("path")] public string Path;
    }

    [Serializable]
    public class ListAssetsParams
    {
        [JsonProperty("type")] public string Type;
        [JsonProperty("path")] public string Path;
    }

    // --- Component operation params ---

    [Serializable]
    public class ComponentOperationParams
    {
        [JsonProperty("path")] public string Path;
        [JsonProperty("target")] public string Target;
    }

    [Serializable]
    public class AddComponentParams : ComponentOperationParams
    {
        [JsonProperty("components")] public List<ComponentDesc> Components;
    }

    [Serializable]
    public class RemoveComponentParams : ComponentOperationParams
    {
        [JsonProperty("componentType")] public string ComponentType;
        [JsonProperty("index")] public int Index;
    }

    [Serializable]
    public class ModifyComponentParams : ComponentOperationParams
    {
        [JsonProperty("componentType")] public string ComponentType;
        [JsonProperty("index")] public int Index;
        [JsonProperty("properties")] public Dictionary<string, object> Properties;
    }

    [Serializable]
    public class InspectComponentParams : ComponentOperationParams
    {
        [JsonProperty("componentType")] public string ComponentType;
        [JsonProperty("index")] public int Index;
    }

    // --- Shared GameObject description ---

    [Serializable]
    public class GameObjectDesc
    {
        [JsonProperty("name")] public string Name = "GameObject";
        [JsonProperty("tag")] public string Tag = "Untagged";
        [JsonProperty("layer")] public string Layer = "Default";
        [JsonProperty("active")] public bool Active = true;
        [JsonProperty("transform")] public TransformDesc Transform;
        [JsonProperty("components")] public List<ComponentDesc> Components;
        [JsonProperty("children")] public List<GameObjectDesc> Children;
    }

    [Serializable]
    public class TransformDesc
    {
        [JsonProperty("position")] public float[] Position;
        [JsonProperty("rotation")] public float[] Rotation;
        [JsonProperty("scale")] public float[] Scale;
    }

    [Serializable]
    public class ComponentDesc
    {
        [JsonProperty("type")] public string Type;
        [JsonProperty("properties")] public Dictionary<string, object> Properties;
    }
}
