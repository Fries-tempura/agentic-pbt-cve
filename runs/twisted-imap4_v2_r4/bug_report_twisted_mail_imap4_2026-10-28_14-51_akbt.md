# Bug Report: twisted.mail.imap4 parseNestedParens raises RecursionError on deeply nested but balanced input

**Target**: `twisted.mail.imap4.parseNestedParens` / `collapseStrings`
**Severity**: Low
**Bug Type**: Crash
**Date**: 2026-10-28

## Summary

`parseNestedParens` raises `RecursionError` when balanced parentheses are nested about 1,000 levels deep. Its documentation lists only `MismatchedNesting`, and only for invalid nesting.

## Property-Based Test

```python
@settings(max_examples=20, deadline=None, database=None)
@given(st.integers(1, 3000))
def test_parse_nested_parens_deep(depth):
    """CLAIM-6: balanced nesting of any depth parses without raising."""
    s = b"(" * depth + b"a" + b")" * depth
    result = imap4.parseNestedParens(s)
    assert isinstance(result, list)
```

**Failing input**: `depth=1000` (depth 900 still parses)

## Reproducing the Bug

```python
from twisted.mail.imap4 import parseNestedParens

parseNestedParens(b"(" * 1000 + b"a" + b")" * 1000)
```

Output: `RecursionError: maximum recursion depth exceeded`

## Why This Is A Bug

The docstring says: "@raise MismatchedNesting: Raised if the number or placement of opening or closing parenthesis is invalid." This input is balanced and about 2 KB long, well under the 16 KB line limit. The parser itself builds the nesting without recursion, using an explicit stack. The recursion is in `collapseStrings`, which calls itself once per nesting level.

The input can come from the network on both sides:

- **Server:** `IMAP4Server.arg_searchkeys` passes a client's SEARCH line to this function. The generic error handler catches the error but reports "Server error" and logs a traceback, instead of a protocol-level BAD.
- **Client:** `IMAP4Client._defaultHandler` parses untagged server responses with it, where the error is not caught.

## Fix

Make `collapseStrings` iterative, using an explicit stack in the same way `parseNestedParens` already does. Alternatively, have `parseNestedParens` enforce a maximum nesting depth (for example 100, far beyond anything in a real IMAP response) and raise `MismatchedNesting`, or a dedicated `IllegalClientResponse`/`IllegalServerResponse`, when it is exceeded. Then the documented error type is raised instead of `RecursionError`.
