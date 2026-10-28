# Claims for litestar.stores.file

## CLAIM-1
- evidence: litestar/stores/file.py:29 — "File based, thread and process safe, asynchronous key/value store."; base.py:26-52 set/get docstrings — "key: Key to associate the value with" / "Returns: The value associated with ``key`` if it exists and is not expired, else ``None``"
- source:   docstring + structure
- reading:  A key/value store associates each key with its own value. `get(k)` must return what was last `set` under `k`, not under some other key. Since storage is one file per key via `_path_from_key` -> `_safe_file_name`, this requires the key-to-filename mapping to be injective. Rules out two distinct keys sharing a slot.
- claim:    For any set of distinct keys k_i set to distinct values v_i (no expiry), get(k_i) == v_i for every i.
- strength: Strongest form: checked against a dict model over many keys at once, not only round trip of a single key (which would pass even with collisions).

## CLAIM-2
- evidence: base.py:40-52 — "Returns: The value associated with ``key`` if it exists ..."
- source:   docstring (round trip)
- reading:  After set(k, v) with no expiry, get(k) must return v (bytes; str encoded utf-8). Any str key is accepted by the annotation `key: str`.
- claim:    For any non-empty str key and bytes value, set then get returns the value.
- strength: Full round trip for every key accepted by the type hint; I did not weaken to "ASCII keys".

## CLAIM-3
- evidence: —
- source:   implicit
- reading:  Must-not-crash: get/exists/delete on a key the API accepts (`key: str`) must not raise an undocumented exception.
- claim:    get(k), exists(k), delete(k) do not raise for any str key.
- strength: Implicit universal expectation.

## CLAIM-4
- evidence: base.py:77-80 / file.py:174-176 — "If no such ``key`` exists or no expiry time was set, return ``None``."
- source:   docstring
- reading:  For a key set with expires_in=None, expires_in(key) must return None. Rules out sentinels like -1.
- claim:    set(k, v) then expires_in(k) is None.
- strength: Direct postcondition.

## CLAIM-5
- evidence: base.py:96-100 — "Bulk actions on a parent namespace should affect all child namespaces, whereas other operations on all namespaces should be isolated."
- source:   docstring
- reading:  A value set in a child namespace must not be visible from the parent under any key, and vice versa.
- claim:    For namespace ns and key k, setting k in child does not make parent.get(k') return it for any k'.
- strength: Checked via keys that could map onto the namespace directory name.

### Amendment (after first run)
- CLAIM-1 test alphabet narrowed to "a3!ﬁf i" — the first alphabet was too wide to hit the
  forged-encoding witness ('!' -> "33"); a hand-built input ('a!' vs 'a33') violated the claim
  while the test passed, so the strategy was fixed rather than the claim.
- CLAIM-2/3 extended with long keys (st.text up to 400 chars, alphabet incl. '/'): the API
  annotates `key: str` with no length limit.
