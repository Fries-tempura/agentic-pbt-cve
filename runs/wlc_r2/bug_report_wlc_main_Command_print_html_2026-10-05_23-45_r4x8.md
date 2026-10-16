# Bug Report: wlc.main.Command.print_html Does Not Escape Values

**Target**: `wlc.main.Command.print_html`
**Severity**: Low
**Bug Type**: Logic
**Date**: 2026-10-05

## Summary

`--format html` puts keys and server-provided values into the HTML without escaping them. Any value that contains markup becomes live HTML.

## Property-Based Test

```python
@given(st.builds(lambda a, t, b: a + "<" + t + ">" + b, st.text(),
                 st.from_regex(r"\A[a-z]{1,6}\Z"), st.text()))
def test_html_output_well_formed(value):
    out = StringIO()
    cmd = Command.__new__(Command)
    cmd.stdout = out
    cmd.args = Namespace(format="html")
    cmd.print({"name": value})
    p = Collect()  # HTMLParser collecting start tags
    p.feed(out.getvalue())
    assert set(p.tags) <= {"table", "tr", "th", "td"}
```

**Failing input**: `value='<a>'`

## Reproducing the Bug

```python
from argparse import Namespace
from io import StringIO
from wlc.main import Command

cmd = Command.__new__(Command)
cmd.stdout = StringIO()
cmd.args = Namespace(format="html")
cmd.print({"name": "<script>alert(1)</script>"})
print(cmd.stdout.getvalue())
```

## Why This Is A Bug

Values such as project names and translation targets come from the server or from translators. If someone renders the HTML report, injected markup or script runs in their browser (stored XSS), and characters like `<` and `&` in ordinary values break the output.

## Fix

```diff
+import html
@@
-                self.println(f"      <th>{key}</th>")
+                self.println(f"      <th>{html.escape(str(key))}</th>")
@@
-                        f"      <td>{self.format_value(getattr(item, key))}</td>"
+                        f"      <td>{html.escape(str(self.format_value(getattr(item, key))))}</td>"
@@
-                self.println(f"    <th>{key}</th><td>{self.format_value(data)}</td>")
+                self.println(f"    <th>{html.escape(str(key))}</th><td>{html.escape(str(self.format_value(data)))}</td>")
```
