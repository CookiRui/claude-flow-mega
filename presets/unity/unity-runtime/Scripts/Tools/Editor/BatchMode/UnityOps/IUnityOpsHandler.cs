namespace {root-namespace}.Tools.BatchMode.UnityOps
{
    /// <summary>
    /// Interface for UnityOps command handlers.
    /// Each handler processes one or more related commands (e.g., scene ops, prefab ops).
    /// </summary>
    public interface IUnityOpsHandler
    {
        OpsResult Execute(OpsCommandEnvelope cmd);
    }
}
