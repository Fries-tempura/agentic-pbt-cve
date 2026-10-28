# Claims for litestar.stores.file

## CLAIM-1
- evidence: file.py:28 — "File based, thread and process safe, asynchronous key/value store." ; base.py get: "The value associated with ``key`` if it exists and is not expired, else ``None``"; set: "key: Key to associate the value with"
- source:   docstring + structure
- reading:  A key/value store associates each key with its own value. `_path_from_key` maps keys to file names, so that mapping must be injective; otherwise setting one key overwrites another. Nothing restricts keys to any character set (annotation is plain `str`).
- claim:    For any distinct keys k1..kn set to distinct values, get(ki) returns the value set for ki.
- strength: Strongest form: full model equality of the store for arbitrary distinct str keys.

## CLAIM-2
- evidence: base.py:26 — `async def set(self, key: str, value: str | bytes, ...)` and get docstring above
- source:   type hint + docstring
- reading:  Any `str` key is accepted; after set(k, v) returns without error, get(k) must return v (bytes / utf-8 encoded). A silently swallowed write would violate this.
- claim:    set(k, v) followed by get(k) returns v (encoded) for every str key k, or set raises.
- strength: Strongest form; no restriction on key length is documented.

## CLAIM-3
- evidence: —
- source:   implicit
- reading:  get/exists/delete accept any str key; they must not raise undocumented exceptions.
- claim:    get(k), exists(k), delete(k) do not raise for any str key.
- strength: universal no-crash expectation.

## CLAIM-4
- evidence: base.py:78 — "Get the time in seconds ``key`` expires in. If no such ``key`` exists or no expiry time was set, return ``None``."
- source:   docstring
- reading:  For a key set with expires_in=None, the return must be None, not a sentinel.
- claim:    After set(k, v) with no expiry, expires_in(k) is None.
- strength: Direct postcondition.

## CLAIM-5
- evidence: base.py:98 — "other operations on all namespaces should be isolated."
- source:   docstring
- reading:  Keys in a child namespace must not collide with keys in the parent.
- claim:    set in namespace ns does not alter get of any key in parent.
- strength: Direct.
