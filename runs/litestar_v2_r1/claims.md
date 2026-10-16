# Claims for litestar.stores.file

## CLAIM-1
- evidence: litestar/stores/file.py:108-118 — get(): "Returns: The value associated with ``key`` if it exists and is not expired, else ``None``"; set(): "key: Key to associate the value with"
- source:   docstring
- reading:  A key/value store associates a value with *the given key*. After set(k, v), get(k) must return v (no expiry). "The value associated with key" rules out returning a value associated with some other key.
- claim:    For any str key k and bytes v, after `await set(k, v)`, `await get(k) == v`.
- strength: Strongest form; round trip on all keys.

## CLAIM-2
- evidence: same as CLAIM-1, plus structure: `_path_from_key` maps each key to a filename via `_safe_file_name`.
- source:   docstring + structure
- reading:  For the store to associate values with keys, distinct keys must map to distinct storage locations; i.e. the key->filename mapping must be injective. Setting k2 must not alter the value associated with k1 != k2.
- claim:    For distinct keys k1 != k2, after set(k1, v1); set(k2, v2): get(k1) == v1 and get(k2) == v2.
- strength: Strongest form (independence of distinct keys). Weaker "round trip for a single key" (CLAIM-1) passes even with collisions.

## CLAIM-3
- evidence: file.py:136-141 — delete(): "Delete a value. If no such key exists, this is a no-op."
- source:   docstring
- reading:  delete(k) removes only k's value. Other keys are unaffected.
- claim:    For distinct keys k1 != k2, after set(k1, v1); delete(k2): get(k1) == v1 and exists(k1) is True.
- strength: Strongest form.
