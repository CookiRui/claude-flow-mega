using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;

namespace {root-namespace}.Tools.AutoTest
{
    public abstract class TestAction
    {
        public Dictionary<string, object> Context { get; set; } = new();

        /// <summary>
        /// Execute the action. Returns true on success, false on failure.
        /// </summary>
        public abstract Task<bool> Execute(CancellationToken ct);

        /// <summary>
        /// Called by JsonTestCaseParser to populate fields from JSON.
        /// </summary>
        public virtual void Configure(Dictionary<string, object> parameters) { }
    }
}
