# Card Text Patches

Create one unified diff patch per note in this directory.

Rules:

- File name: `<note-id>.patch`
- Target field: `fields.Text`
- Base text comes from `editable/notes/<note-id>.yaml`
- Patches are applied only at build time

Example header:

```diff
--- a/text
+++ b/text
@@ -1 +1 @@
-old line
+new line
```
