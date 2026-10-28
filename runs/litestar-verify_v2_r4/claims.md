# Claims for litestar.stores.file

## CLAIM-1
- evidence: base.py:26-52 — Store.set: "key: Key to associate the value with"; Store.get: "Returns: The value associated with ``key`` if it exists and is not expired, else ``None``"
- source:   docstring
- reading:  A key/value store associates each value with *its* key. After set(k1, v1), set(k2, v2) with k1 != k2, get(k1) must return v1 — writing a different key must not overwrite it. This rules out any key→storage-location mapping that is not injective (FileStore maps keys to file names via _safe_file_name, file.py:23-25).
- claim:    For any set of distinct keys each set to a distinct value, get(k) returns the value set for k.
- strength: Strongest form; equivalent to injectivity of key→file mapping, checked via the public API across all pairs in a list.

## CLAIM-2
- evidence: base.py:78-79 — "Get the time in seconds ``key`` expires in. If no such ``key`` exists or no expiry time was set, return ``None``." (FileStore.expires_in docstring file.py:175-176 says the same)
- source:   docstring
- reading:  Two cases explicitly return None: missing key, and key set without expiry.
- claim:    After set(k, v) with expires_in=None, expires_in(k) is None.
- strength: Direct postcondition, no weakening.

## CLAIM-3
- evidence: file.py:89-106 set() with no documented exception; base.py "Set a value"
- source:   implicit (set followed by get must round trip; failure must not be silent)
- reading:  Store.set has no documented failure mode; a set that returns normally must make the value retrievable. Silently dropping a write is data loss. Keys in Litestar are arbitrary strings (e.g. cache keys built from URL path + query).
- claim:    For any str key and bytes value, after `await set(k, v)` returns normally, `await get(k) == v`.
- strength: Round-trip; strongest form.

## CLAIM-4
- evidence: base.py:98 — "Bulk actions on a parent namespace should affect all child namespaces"; file.py:157-163 delete_expired "Delete expired items."
- source:   docstring
- reading:  delete_expired is a bulk action. On a parent store with a child namespace it must not crash, and should delete expired items in children too.
- claim:    After store.with_namespace(ns).set(...), store.delete_expired() completes without raising, and expired items in the child are removed.
- strength: Strongest: includes both no-crash and propagation.

## CLAIM-5
- evidence: base.py:26-80 (set/delete/exists sequence)
- source:   sequence
- reading:  exists(k) reflects set/delete history: True after set (no expiry), False after delete.
- claim:    For any sequence of set/delete on keys, exists(k) == (k in model) and get(k) == model[k].
- strength: Model-based; strongest.
