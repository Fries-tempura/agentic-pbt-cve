# Claims for litestar.stores.file

## CLAIM-1
- evidence: litestar/stores/file.py:117-119 — "The value associated with ``key`` if it exists and is not expired, else ``None``"; file.py:95 — "key: Key to associate the value with"
- source:   docstring
- reading:  `get(k)` returns the value associated with *that* key. Two distinct keys are two
            distinct associations; nothing in the docstring restricts the key alphabet (type hint
            is plain `str`). So after set(k1,v1); set(k2,v2) with k1 != k2, get(k1) must be v1.
            Structurally, `_path_from_key`/`_safe_file_name` is a key-to-filename mapping, which
            therefore must be injective.
- claim:    For any list of distinct str keys each set to a distinct value, get(k) returns
            exactly the value set for k.
- strength: Strongest form: full key/value model equality, not merely "get returns something".

## CLAIM-2
- evidence: file.py:139 — "If no such key exists, this is a no-op." and file.py:170 — "Check if a given ``key`` exists."
- source:   docstring
- reading:  delete(k) removes k only; exists(k) reports exactly whether k currently has a value.
- claim:    After any sequence of set/delete, exists(k) and get(k) agree with a dict model.
- strength: Checked via a state machine over all keys, strongest available.

## CLAIM-3
- evidence: base.py:97-98 — "Bulk actions on a parent namespace should affect all child namespaces, whereas other operations on all namespaces should be isolated."
- source:   docstring
- reading:  set/get/delete in a parent store must not interfere with a child namespace store and
            vice-versa; bulk ops (delete_expired, delete_all) on the parent must work with child
            namespaces present.
- claim:    Keys in parent and in child namespace are independent; parent.delete_expired()
            succeeds (no exception) when child namespaces exist.
- strength: Full isolation in both directions.

## CLAIM-4
- evidence: —
- source:   implicit
- reading:  Universal expectation: a `set` that returns normally has stored the value (it does not
            document silent failure); `get` immediately after must return it (no expiry given).
- claim:    For any str key, set(k, v) followed by get(k) returns v.
- strength: Strongest form.

## Notes after testing
- CLAIM-1 test initially passed with alphabet "ab09-_./:..." — it could not fail, because
  ord('-') == 45 needs digits 4 and 5. The alphabet now has all digits; it fails as expected.
- CLAIM-4: the 1-char failure '\U00013460' is APFS rejecting an unassigned (to it) code point
  (EILSEQ) — platform-specific, not filed. The long-key failure is filed.
