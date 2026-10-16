import importlib.util
from hypothesis import given, settings, strategies as st
import configobj.validate as orig

spec = importlib.util.spec_from_file_location("pv", "patched/configobj/validate.py")
pv = importlib.util.module_from_spec(spec); spec.loader.exec_module(pv)

@settings(max_examples=3000)
@given(st.text(alphabet="ab =,'\"()l", max_size=30))
def test_same_parse(args):
    s = "f(" + args + ")"
    try:
        new = pv.Validator()._parse_check(s)
    except pv.VdtParamError:
        return
    assert orig.Validator()._parse_check(s) == new
