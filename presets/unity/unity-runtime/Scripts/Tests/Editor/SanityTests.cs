using NUnit.Framework;

namespace {root-namespace}.Tests
{
    /// <summary>
    /// Minimal sanity tests — verifies the test pipeline and assembly references work.
    /// </summary>
    public class SanityTests
    {
        [Test]
        public void TrueIsTrue()
        {
            Assert.That(true, Is.True);
        }

        [Test]
        public void AssemblyReferencesWork()
        {
            // Verify that the Tools.Editor assembly is reachable.
            // If this compiles, the asmdef reference chain is valid.
            var type = typeof(Gameplay.AutoTest.IInputProvider);
            Assert.That(type, Is.Not.Null);
        }
    }
}
