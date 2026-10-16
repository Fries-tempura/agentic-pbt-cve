# Bug Report: configobj.validate list(...) keyword with empty quoted string swallows following arguments

**Target**: `configobj.validate.Validator` (check-string parsing, `_paramstring` / `_list_arg` / `_list_members`)
**Severity**: Medium
**Bug Type**: Logic
**Date**: 2026-10-06

## Summary

Suppose a `key=list(...)` argument ends with an empty quoted string `""`, and the next argument is another `list(...)` that starts with a quoted string. The parser then merges the two arguments into one. The first keyword gets a garbage value, and the second keyword is lost. That includes `default`.

## Property-Based Test

```python
from hypothesis import given, settings, strategies as st, assume
from configobj.validate import Validator

ident = st.from_regex(r'[a-zA-Z_][a-zA-Z0-9_]{0,8}', fullmatch=True)
plain = st.from_regex(r'[a-zA-Z0-9_.+-]{1,10}', fullmatch=True)
quoted_body = st.text(alphabet=st.characters(blacklist_characters='"\'', blacklist_categories=('Cs',)), max_size=10)
value = st.one_of(plain, quoted_body.map(lambda s: '"%s"' % s))

def unq(v):
    return v[1:-1] if len(v) >= 2 and v[0] == v[-1] and v[0] in '"\'' else v

@settings(max_examples=500, deadline=None)
@given(name=ident, args=st.lists(value, max_size=4),
       kwargs=st.dictionaries(ident.filter(lambda k: k != 'default'), value, max_size=3),
       lists=st.dictionaries(ident.filter(lambda k: k != 'default'), st.lists(value, max_size=4), max_size=2))
def test_parse_check_roundtrip(name, args, kwargs, lists):
    assume(not set(kwargs) & set(lists))
    parts = list(args) + ['%s=%s' % kv for kv in kwargs.items()] + \
        ['%s=list(%s)' % (k, ', '.join(v)) for k, v in lists.items()]
    check = '%s(%s)' % (name, ', '.join(parts))
    fname, fargs, fkw, default = Validator()._parse_check(check)
    assert fname == name
    assert fargs == [unq(a) for a in args]
    for k, val in kwargs.items():
        exp = val if val in ("'None'", '"None"') else unq(val)
        assert fkw[k] == exp
    for k, vals in lists.items():
        assert fkw[k] == [unq(x) for x in vals]
```

**Failing input**: `name='A', args=[], kwargs={}, lists={'B': ['""'], 'A': ['""', '""']}`, i.e. the check `A(B=list(""), A=list("", ""))`

## Reproducing the Bug

```python
from configobj.validate import Validator

v = Validator()
print(v._parse_check('f(a=list(""), b=list("x", "y"))'))
print(v._parse_check('f(a=list(""), default=list("x", "y"))'))
```

Output:
```
('f', [], {'a': ['"), b=list("x', 'y']}, None)
('f', [], {'a': ['"), default=list("x', 'y']}, None)
```

Expected: `{'a': [''], 'b': ['x', 'y']}`. In the second case, the expected default is `['x', 'y']`.

## Why This Is A Bug

The `key=list(val, val)` syntax is documented, and an empty string is a valid list member. Writing `f(a=list("x", ""), b=list("y"))` or `f(a=list(""), b="z")` parses correctly, so the failure depends only on the position of the empty string. This is silent data corruption: the check function gets wrong arguments, and the configured `default` disappears with no error. The cause is the lazy quoted-string alternatives `".*?"` / `'.*?'`. After `list("` they can match `"), b=list("` as one "quoted string".

## Fix

Quoted strings should not be allowed to contain their own quote character. In `_list_arg`, `_list_members` and `_paramstring`, replace every occurrence of:

```diff
-                        (?:".*?")|              # double quotes
-                        (?:'.*?')|              # single quotes
+                        (?:"[^"]*")|            # double quotes
+                        (?:'[^']*')|            # single quotes
```

After this change, `f(a=list(""), default=list("x", "y"))` parses as `('f', [], {'a': ['']}, ['x', 'y'])`.
