## Summary

`Array.__delitem__` keeps the in-memory list and the rendered value groups in sync, but for **slice** deletions it recomputes which rendered positions to drop with:

```python
range(key.start or 0, key.stop or length, key.step or 1)
```

This mishandles ordinary slices:

- `stop == 0` (`a[:0]`): `0 or length` evaluates to `length`, so a no-op deletion removes **every** rendered element.
- negative bounds aren't normalized: `a[-1:]` → `range(-1, length)`, and `a[:-1]` → `range(0, -1)` (empty, removes nothing).

`list.__delitem__` handles the slice correctly, so the list contents stay right, but `as_string()` / `dumps()` silently disagree with them:

```python
import tomlkit
doc = tomlkit.parse("a = [1, 2, 3]\n")
del doc["a"][:0]        # deletes nothing
tomlkit.dumps(doc)      # 'a = []\n'  — expected 'a = [1, 2, 3]\n'
```

| operation | `list(arr)` | `arr.as_string()` | expected |
|---|---|---|---|
| `del arr[:0]`  | `[1, 2, 3]` | `[]`        | `[1, 2, 3]` |
| `del arr[-1:]` | `[1, 2]`    | `[]`        | `[1, 2]`    |
| `del arr[:-1]` | `[3]`       | `[1, 2, 3]` | `[3]`       |

**Fix:** use `slice.indices(length)`, which resolves `None`, negative, and out-of-range bounds exactly the way `list.__delitem__` does, so the removed render positions always match the list.

**Tests:** added `test_array_slice_deletion_keeps_render_in_sync` covering `a[:0]`, `a[-1:]`, and `a[:-1]`. Full `tests/test_items.py` passes (87 passed).

## Agent Drafting Metadata

- Agent: Claude Code (property-based testing workflow)
- Model: Claude Opus 5
- Notes: The bug was found by property-based testing (Hypothesis) run against `main`. The one-line fix and the regression test were drafted with the agent and verified locally — the repro fails before the change and `tests/test_items.py` passes (87 passed) after. Reviewed by the submitter before opening.
