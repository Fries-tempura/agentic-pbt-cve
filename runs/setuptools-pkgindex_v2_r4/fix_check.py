import re, time
from hypothesis import given, settings, strategies as st
from setuptools.package_index import REL
TAG = re.compile(r"<([^>]*)>")
RELATTR = re.compile(r"""\srel\s{0,10}=\s{0,10}['"]?([^'" >]+)""", re.I)
def new(page):
    for chunk in page.split(">")[:-1]:
        start = chunk.find("<")
        if start == -1: continue
        tag = chunk[start + 1:]
        r = RELATTR.search(tag)
        if r: yield tag, r.group(1)
def old(page): return [m.groups() for m in REL.finditer(page)]
@settings(max_examples=3000)
@given(st.lists(st.sampled_from(["<", ">", " rel", "=", '"', "'", "x", " ", "homepage", "a", "\t", ","]), max_size=30).map("".join))
def test_same(p): assert list(new(p)) == old(p), p
test_same()
p = "< rel=" * 20000; t = time.perf_counter(); list(new(p)); print("fixed, 120k chars:", round(time.perf_counter()-t, 3), "s")
