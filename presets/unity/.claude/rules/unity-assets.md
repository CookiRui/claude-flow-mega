---
paths:
  - "{unity-project-dir}/Assets/**/*.unity"
  - "{unity-project-dir}/Assets/**/*.prefab"
  - "{unity-project-dir}/Assets/**/*.mat"
  - "{unity-project-dir}/Assets/**/*.controller"
  - "{unity-project-dir}/Assets/**/*.anim"
  - "{unity-project-dir}/Assets/**/*.asset"
  - "{unity-project-dir}/Assets/**/*.meta"
---

# Unity Asset Rules

## CRITICAL: Never Do
- NEVER modify `fileID` or `GUID` values in any asset file
- NEVER manually create `.meta` files (Unity Editor generates them)
- NEVER delete `.meta` files without deleting the corresponding asset
- NEVER edit binary assets (textures, models, audio) as text

## .meta File Integrity
- Every file and folder under Assets/ has a corresponding `.meta` file
- When adding a new file, Unity must generate its `.meta` — do not create it by hand
- When deleting a file, always delete the `.meta` file as well
- When moving/renaming a file, move/rename the `.meta` file in the same operation
- Orphaned `.meta` files (without a corresponding asset) cause import errors

## YAML Editing
- Unity assets use Force Text serialization (YAML format)
- Preserve exact indentation and formatting when editing
- Do not reorder fields; Unity expects specific field ordering
- When unsure about YAML structure, read the existing file first

## Scene & Prefab
- Prefer prefab-based workflows over scene-heavy setups
- Use prefab variants for specialized versions of base prefabs
- Keep scene hierarchy flat and organized by function
- Avoid editing scenes in text mode unless the change is trivial and well-understood

## Self-check Checklist

- [ ] Have any `fileID` or `GUID` values been modified?
- [ ] Does every new/deleted asset have its `.meta` file handled correctly?
- [ ] Is YAML indentation preserved exactly as the original?
