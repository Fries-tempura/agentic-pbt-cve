import os
import posixpath
import tempfile

import pytest
from hypothesis import assume, given, settings, strategies as st

from mako import exceptions
from mako import lookup

BASE = tempfile.mkdtemp(prefix="mako_pbt3_")
TMPL_DIR = os.path.join(BASE, "templates")
os.makedirs(os.path.join(TMPL_DIR, "subdir"))
for p in ("index.html", "subdir/index.html"):
    with open(os.path.join(TMPL_DIR, p), "w") as f:
        f.write("hello")


# ---------------------------------------------------------------------------
# Property 1: adjust_uri must not blow up with a non-TemplateLookupException
# on a uri a template author can actually write.
# ---------------------------------------------------------------------------
@settings(max_examples=500)
@given(st.text(max_size=20), st.one_of(st.none(), st.text(max_size=20)))
def test_adjust_uri_no_unexpected_crash(uri, relativeto):
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    try:
        result = tl.adjust_uri(uri, relativeto)
    except exceptions.MakoException:
        return
    assert isinstance(result, str)


def test_adjust_uri_empty_via_include():
    """An <%include file=''/> in a template -- realistic template-author
    input -- should raise a Mako exception, not IndexError."""
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    tl.put_string("caller.html", "<%include file=''/>")
    with pytest.raises(exceptions.MakoException):
        tl.get_template("caller.html").render()


# ---------------------------------------------------------------------------
# Property 2: _relativeize / filename_to_uri round-trip.
#
# filename_to_uri is documented to "Return the portion of a filename that is
# 'relative' to the directories in this lookup".  A file that is NOT under any
# of the directories has no such portion -> None.
# ---------------------------------------------------------------------------
dirnames = st.lists(
    st.sampled_from(["foo", "bar", "baz"]), min_size=1, max_size=3
).map(lambda s: "/" + "/".join(s))

names = st.text(alphabet="abz_-", min_size=1, max_size=4)


@settings(max_examples=1000)
@given(dirnames, names, names)
def test_filename_to_uri_only_claims_files_under_a_directory(
    directory, sibling_suffix, leaf
):
    """If filename_to_uri returns a uri for a filename, then joining that
    uri back onto the lookup directory must give the original filename."""
    assume(sibling_suffix != "")
    tl = lookup.TemplateLookup(directories=[directory])
    filename = directory + sibling_suffix + "/" + leaf + ".html"

    uri = tl.filename_to_uri(filename)
    if uri is None:
        return
    rejoined = posixpath.normpath(
        posixpath.join(directory, uri.lstrip("/"))
    )
    assert rejoined == posixpath.normpath(filename), (
        f"directories={[directory]!r} filename={filename!r} -> uri={uri!r}, "
        f"which maps back to {rejoined!r}"
    )
