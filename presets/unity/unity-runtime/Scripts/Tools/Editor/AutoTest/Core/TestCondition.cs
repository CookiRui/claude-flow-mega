using System.Collections.Generic;

namespace {root-namespace}.Tools.AutoTest
{
    public abstract class TestCondition
    {
        /// <summary>
        /// Check if the condition is met. Must be non-blocking.
        /// </summary>
        public abstract bool Check();

        /// <summary>
        /// Descriptive message when condition fails.
        /// </summary>
        public virtual string FailMessage => GetType().Name + " not met";

        /// <summary>
        /// Called by JsonTestCaseParser to populate fields from JSON.
        /// </summary>
        public virtual void Configure(Dictionary<string, object> parameters) { }
    }
}
