using UnityEngine;

namespace {root-namespace}.Gameplay.AutoTest
{
    /// <summary>
    /// Singleton bridge between editor automation and gameplay input.
    /// Survives scene loads via DontDestroyOnLoad.
    /// </summary>
    public class AutoTestBridge : MonoBehaviour
    {
        private static AutoTestBridge _instance;
        public static AutoTestBridge Instance => _instance;

        private TestInputProvider _testInput;
        public TestInputProvider TestInput => _testInput;

        private void Awake()
        {
            if (_instance != null && _instance != this)
            {
                Destroy(gameObject);
                return;
            }
            _instance = this;
            _testInput = new TestInputProvider();
            DontDestroyOnLoad(gameObject);
            Debug.Log("[AutoTestBridge] Initialized");
        }

        private void LateUpdate()
        {
            _testInput?.ClearFrameState();
        }

        private void OnDestroy()
        {
            if (_instance == this)
                _instance = null;
        }

        // === Input Bridge Methods (called by Editor AutoTest Actions) ===

        public void SetMovementInput(Vector2 input)
        {
            _testInput?.SetMovement(input);
        }

        public void PressButton(string buttonName)
        {
            _testInput?.PressButton(buttonName);
        }

        public void ReleaseButton(string buttonName)
        {
            _testInput?.ReleaseButton(buttonName);
        }

        // === Query Methods ===

        public static GameObject FindGameObject(string nameOrPath)
        {
            return GameObject.Find(nameOrPath);
        }

        public static T FindComponent<T>(string gameObjectName) where T : Component
        {
            var go = GameObject.Find(gameObjectName);
            if (go == null) return null;
            return go.GetComponent<T>();
        }
    }
}
