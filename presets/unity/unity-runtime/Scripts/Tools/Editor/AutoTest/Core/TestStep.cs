namespace {root-namespace}.Tools.AutoTest
{
    public class TestStep
    {
        public string Name;
        public TestAction Action;
        public TestCondition PreCondition;
        public TestCondition PostCondition;
        public float WaitAfterAction = 0.5f;
        public float Timeout = 5f;
        public float PollingInterval = 0.1f;
        public int RetryCount = 0;
        public float RetryDelay = 1f;
        public FailPolicy FailPolicy = FailPolicy.Continue;
        public string[] CaptureContext;
    }

    public enum FailPolicy { Continue, Abort }
    public enum StepResult { Pending, Running, Passed, Failed, Timeout, Skipped }
}
