import time
from hypothesis import given, settings, strategies as st
from pygments.lexers.archetype import AdlLexer
from pygments.token import Error, Whitespace
from patched import PatchedAdl

alphabet = st.sampled_from(list('aZv09_-.:|[](){}<>/"\' \t\n,;=*+@'))
words = st.sampled_from(['archetype', 'definition', 'language', 'rules', 'description',
                         'openEHR-EHR-OBSERVATION.bp.v1', 'x.aa-bb-cc.d.v2.0', '(adl_version=2.0)'])
text = st.lists(st.one_of(st.text(alphabet, max_size=5), words)).map(''.join)


def norm(toks):
    # merge, and treat lone Error spaces as Whitespace (the only intended change)
    out = []
    for t, v in toks:
        if t is Error and v.strip(' \t') == '':
            t = Whitespace
        if out and out[-1][0] is t:
            out[-1] = (t, out[-1][1] + v)
        else:
            out.append((t, v))
    return out


@settings(max_examples=2000, deadline=None)
@given(text)
def test_patch_equivalent(s):
    a = norm(AdlLexer(stripnl=False).get_tokens(s))
    b = norm(PatchedAdl(stripnl=False).get_tokens(s))
    assert a == b


@settings(max_examples=20, deadline=None)
@given(st.integers(4000, 16000), st.sampled_from(['a', ' ', 'aa-aa-aa.a']))
def test_patched_fast(n, ch):
    s = ch * n
    t = time.perf_counter()
    list(PatchedAdl().get_tokens(s))
    assert time.perf_counter() - t < 0.5
