import time
from hypothesis import given, settings, strategies as st
from black.strings import lines_with_leading_tabs_expanded as orig

def fixed(s):
    lines = []
    for line in s.splitlines():
        stripped_line = line.lstrip()
        if not stripped_line or stripped_line == line:
            lines.append(line)
        else:
            prefix_length = len(line) - len(stripped_line)
            prefix = line[:prefix_length]
            if "\t" in prefix:
                lines.append(prefix.expandtabs() + stripped_line)
            else:
                lines.append(line)
    if s.endswith("\n"):
        lines.append("")
    return lines

@settings(max_examples=3000)
@given(st.text(st.sampled_from(" \t\x0b\x0c　ab\n\r"), max_size=30))
def test_equiv(s):
    assert fixed(s) == orig(s)

def test_fast():
    t = time.perf_counter(); fixed("\t" * 100000); assert time.perf_counter() - t < 0.5
