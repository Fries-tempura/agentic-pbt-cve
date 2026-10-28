# Claims for litestar.stores.file

## CLAIM-1
- evidence: litestar/stores/base.py:21 — "Thread and process safe asynchronous key/value store."; base.py:27-33 — "Set a value. ... key: Key to associate the value with"; base.py:49-50 — "The value associated with ``key`` if it exists and is not expired, else ``None``"
- source:   docstring + structure
- reading:  A key/value store associates each value with *its* key. `get(k)` returns "the value associated with k": the value from the most recent `set(k, ...)`, or None if k was never set. Setting a different key k2 must not change what is associated with k. FileStore maps keys to file names via `_safe_file_name`; for the store contract to hold, that mapping must be injective over distinct keys.
- claim:    For distinct keys k1 != k2, after set(k1, v1); set(k2, v2): get(k1) == v1 and get(k2) == v2.
- strength: Strongest form: every set key independently keeps its value. Weaker "get(k) after set(k) returns v" alone would miss cross-key collisions.

## CLAIM-2
- evidence: base.py:73 — "Check if a given ``key`` exists."
- source:   docstring
- reading:  exists(k) is True only if k was set (and not deleted). A key that was never set must not "exist" because another key was set.
- claim:    After setting only k1, exists(k2) is False for every k2 != k1.
- strength: Full form.

## CLAIM-3
- evidence: base.py:57-59 — "Delete a value. If no such key exists, this is a no-op."
- source:   docstring
- reading:  delete(k2) removes only k2's value; for another key k1 it is a no-op on k1.
- claim:    set(k1, v); delete(k2) with k2 != k1 leaves get(k1) == v.
- strength: Full form.

## CLAIM-4
- evidence: —
- source:   implicit
- reading:  Every key accepted by the `str`-annotated API should not crash set/get with an undocumented exception; set must not silently drop data that get then cannot return.
- claim:    For any str key, set(k, v) followed by get(k) returns v without raising.
- strength: Strong form: round trip holds for every str key, including empty and long.
