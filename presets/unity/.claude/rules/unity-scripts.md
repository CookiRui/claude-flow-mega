---
paths:
  - "{unity-project-dir}/Assets/**/*.cs"
---

# Unity C# Script Rules

## Naming Conventions
- Namespace: `{root-namespace}.<Feature>` (maps to Scripts/<Feature>/ directory)
- Types/Methods: PascalCase (`PlayerController`, `TakeDamage`)
- Local variables/parameters: camelCase (`moveSpeed`, `targetPosition`)
- Private fields: `_camelCase` with underscore prefix (`_health`, `_rigidbody`)
- Constants: PascalCase (`MaxHealth`, `DefaultSpeed`)
- MonoBehaviour filename MUST match class name exactly

## Component Patterns
- Use `[SerializeField] private` instead of `public` fields for Inspector exposure
- Cache components in `Awake()` or `Start()`, NEVER call `GetComponent<T>()` in `Update()`
- Use `TryGetComponent<T>()` when component may not exist
- Prefer composition over inheritance for game logic

## Performance
- Avoid LINQ in hot paths (Update, FixedUpdate, LateUpdate)
- Avoid allocations in hot paths: no `new`, no string concatenation, no boxing
- Use `CompareTag()` instead of `== "tag"`
- Use object pooling for frequently spawned/destroyed objects
- Cache `transform` reference if accessed multiple times per frame

```csharp
// ✅ Correct
private Transform _cachedTransform;

private void Awake()
{
    _cachedTransform = transform;
    _rb = GetComponent<Rigidbody>();
}

private void Update()
{
    if (other.CompareTag("Player")) { /* ... */ }
}

// ❌ Wrong
private void Update()
{
    var rb = GetComponent<Rigidbody>();           // allocation every frame
    if (other.tag == "Player") { /* ... */ }       // string allocation + comparison
    var items = enemies.Where(e => e.IsAlive);     // LINQ in hot path
}
```

## Assembly Definitions
- Each feature folder under Scripts/ should have its own .asmdef
- Reference only the assemblies you actually need
- Keep circular dependencies at zero
- {assembly-definition-rules — e.g., naming convention like "{root-namespace}.Feature", shared assembly names}

## Documentation
- XML doc comments on public API only
- Keep comments minimal; prefer self-documenting code

## Self-check Checklist

- [ ] Does every MonoBehaviour filename match its class name?
- [ ] Are all `GetComponent<T>()` calls outside of Update/FixedUpdate/LateUpdate?
- [ ] Are all tag comparisons using `CompareTag()` instead of `==`?
- [ ] Are Inspector-exposed fields using `[SerializeField] private` instead of `public`?
