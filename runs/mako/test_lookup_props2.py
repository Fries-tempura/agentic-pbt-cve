import os
import posixpath
import tempfile

from hypothesis import given, settings, strategies as st

from mako import exceptions
from mako import lookup

BASE = tempfile.mkdtemp(prefix="mako_pbt2_")
TMPL_DIR = os.path.join(BASE, "app", "templates")
os.makedirs(os.path.join(TMPL_DIR, "subdir"))
with open(os.path.join(TMPL_DIR, "index.html"), "w") as f:
    f.write("this is index")
with open(os.path.join(TMPL_DIR, "subdir", "index.html"), "w") as f:
    f.write("this is sub index")
SECRET_DIR = os.path.join(BASE, "secrets")
os.makedirs(SECRET_DIR)
with open(os.path.join(SECRET_DIR, "creds.txt"), "w") as f:
    f.write("SECRET_KEY=supersecret123")


def _is_inside(filename, directory):
    filename = posixpath.normpath(os.path.abspath(filename))
    directory = posixpath.normpath(os.path.abspath(directory))
    return filename == directory or filename.startswith(directory + "/")


SEGMENTS = st.one_of(
    st.sampled_from(
        [
            "..",
            ".",
            "",
            "...",
            "/",
            "//",
            "\\",
            "..\\",
            "app",
            "templates",
            "secrets",
            "creds.txt",
            "index.html",
            "subdir",
        ]
    ),
    st.text(alphabet=".\\/ actersx", max_size=6),
)

uris = st.builds(
    lambda segs: "/".join(segs),
    st.lists(SEGMENTS, min_size=1, max_size=8),
)


@settings(max_examples=5000)
@given(uris)
def test_no_escape(uri):
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    try:
        tmpl = tl.get_template(uri)
    except exceptions.TemplateLookupException:
        return
    assert _is_inside(tmpl.filename, TMPL_DIR), (
        f"uri {uri!r} escaped: {tmpl.filename!r}"
    )


@settings(max_examples=5000)
@given(uris, uris)
def test_no_escape_via_adjust_uri(uri, relativeto):
    """The runtime (<%include>/<%namespace>) path: adjust_uri then
    get_template."""
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    try:
        adjusted = tl.adjust_uri(uri, relativeto)
        tmpl = tl.get_template(adjusted)
    except exceptions.TemplateLookupException:
        return
    assert _is_inside(tmpl.filename, TMPL_DIR), (
        f"uri {uri!r} rel {relativeto!r} -> {adjusted!r} escaped: "
        f"{tmpl.filename!r}"
    )
