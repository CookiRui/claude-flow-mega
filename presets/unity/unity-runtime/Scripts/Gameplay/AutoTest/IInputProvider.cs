using UnityEngine;

namespace {root-namespace}.Gameplay.AutoTest
{
    /// <summary>
    /// Abstraction layer for input — swap between real Unity input and
    /// deterministic test input without changing gameplay code.
    /// </summary>
    public interface IInputProvider
    {
        Vector2 GetMovementInput();
        bool GetButtonDown(string buttonName);
        bool GetButtonUp(string buttonName);
        bool GetButton(string buttonName);
    }
}
