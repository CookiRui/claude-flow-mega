using UnityEngine;

namespace {root-namespace}.Gameplay.AutoTest
{
    /// <summary>
    /// Real Unity Input.* wrapper — used in production builds.
    /// </summary>
    public class UnityInputProvider : IInputProvider
    {
        public Vector2 GetMovementInput()
        {
            return new Vector2(Input.GetAxis("Horizontal"), Input.GetAxis("Vertical"));
        }

        public bool GetButtonDown(string buttonName) => Input.GetButtonDown(buttonName);
        public bool GetButtonUp(string buttonName) => Input.GetButtonUp(buttonName);
        public bool GetButton(string buttonName) => Input.GetButton(buttonName);
    }
}
