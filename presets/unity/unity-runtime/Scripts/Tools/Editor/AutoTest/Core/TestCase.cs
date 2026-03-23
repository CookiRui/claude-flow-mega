using System.Collections.Generic;

namespace {root-namespace}.Tools.AutoTest
{
    public class TestCase
    {
        public string Id;
        public string Scene;
        public string Name;
        public string Description;
        public float MaxDuration = 120f;
        public Dictionary<string, string> Parameters = new();
        public TestStep[] Setup;
        public TestStep[] Steps;
        public TestStep[] Cleanup;
    }
}
