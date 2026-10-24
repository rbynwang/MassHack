---
inclusion: fileMatch
fileMatchPattern: ["app/presentation/**"]
---

# Presentation scenes

When working on the 3D presentation in `app/presentation/`, follow its handoff notes:

#[[file:app/presentation/README.md]]

Key rules: all on-screen words and numbers live in `story-data.js`; the player must work offline with no WebGL;
re-render stills with `commonwatt-bake.html` after changing cameras, buildings, flows or label anchors; label
anything not measured as illustrative or simulated; generic product names only.
