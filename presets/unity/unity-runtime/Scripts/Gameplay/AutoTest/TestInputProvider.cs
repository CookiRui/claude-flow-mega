using System.Collections.Generic;
using UnityEngine;

namespace {root-namespace}.Gameplay.AutoTest
{
    /// <summary>
    /// Deterministic input provider for automated tests.
    /// Zero allocation after initialization — uses pre-allocated HashSets
    /// with frame-based button state tracking.
    /// </summary>
    public class TestInputProvider : IInputProvider
    {
        private Vector2 _movement;
        private readonly HashSet<string> _pressedButtons = new();
        private readonly HashSet<string> _downThisFrame = new();
        private readonly HashSet<string> _upThisFrame = new();

        public void SetMovement(Vector2 value) => _movement = value;

        public void PressButton(string name)
        {
            _pressedButtons.Add(name);
            _downThisFrame.Add(name);
        }

        public void ReleaseButton(string name)
        {
            _pressedButtons.Remove(name);
            _upThisFrame.Add(name);
        }

        /// <summary>
        /// Must be called at end of frame (LateUpdate) to reset per-frame state.
        /// </summary>
        public void ClearFrameState()
        {
            _downThisFrame.Clear();
            _upThisFrame.Clear();
        }

        public Vector2 GetMovementInput() => _movement;
        public bool GetButtonDown(string name) => _downThisFrame.Contains(name);
        public bool GetButtonUp(string name) => _upThisFrame.Contains(name);
        public bool GetButton(string name) => _pressedButtons.Contains(name);

        public void Reset()
        {
            _movement = Vector2.zero;
            _pressedButtons.Clear();
            _downThisFrame.Clear();
            _upThisFrame.Clear();
        }
    }
}
