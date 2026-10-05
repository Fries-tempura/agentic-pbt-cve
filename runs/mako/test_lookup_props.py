import os
import posixpath
import shutil
import tempfile

import pytest
from hypothesis import given, settings, strategies as st

from mako import exceptions
from mako import lookup


# ---------------------------------------------------------------------------
# Fixture tree:
#
#   base/
#     app/templates/index.html     <- the one and only lookup directory
#     secrets/creds.txt            <- must never be reachable
#
# ---------------------------------------------------------------------------
BASE = tempfile.mkdtemp(prefix="mako_pbt_")
TMPL_DIR = os.path.join(BASE, "app", "templates")
os.makedirs(os.path.join(TMPL_DIR, "subdir"))
with open(os.path.join(TMPL_DIR, "index.html"), "w") as f:
    f.write("this is index")
with open(os.path.join(TMPL_DIR, "subdir", "index.html"), "w") as f:
    f.write("this is sub index")
SECRET_DIR = os.path.join(BASE, "secrets")
os.makedirs(SECRET_DIR)
SECRET = os.path.join(SECRET_DIR, "creds.txt")
with open(SECRET, "w") as f:
    f.write("SECRET_KEY=supersecret123")


SEGMENTS = st.sampled_from(
    [
        "..",
        ".",
        "",
        "app",
        "templates",
        "secrets",
        "creds.txt",
        "index.html",
        "subdir",
    ]
)

uris = st.builds(
    lambda slashes, segs: "/" * slashes + "/".join(segs),
    st.integers(min_value=0, max_value=3),
    st.lists(SEGMENTS, min_size=1, max_size=8),
)


def _is_inside(filename, directory):
    """Lexical containment check: is ``filename`` under ``directory``?"""
    filename = posixpath.normpath(os.path.abspath(filename))
    directory = posixpath.normpath(os.path.abspath(directory))
    return filename == directory or filename.startswith(directory + "/")


@settings(max_examples=2000)
@given(uris)
def test_get_template_never_escapes_lookup_directories(uri):
    """:class:`.TemplateLookup` documents that a URI is "appended to each
    directory and the filesystem checked", and :class:`.Template` explicitly
    rejects a uri that "cannot be relative outside of the root path".

    So: whatever uri is handed to ``get_template``, the template that comes
    back must live inside one of the lookup directories.
    """
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    try:
        tmpl = tl.get_template(uri)
    except exceptions.TemplateLookupException:
        return
    assert _is_inside(tmpl.filename, TMPL_DIR), (
        f"uri {uri!r} escaped the lookup directory: {tmpl.filename!r}"
    )


@settings(max_examples=500)
@given(uris)
def test_has_template_agrees_with_get_template(uri):
    """``has_template`` is documented to return True iff the lookup is
    "capable of returning a Template object for the given uri"."""
    tl = lookup.TemplateLookup(directories=[TMPL_DIR])
    if tl.has_template(uri):
        tl.get_template(uri)


def teardown_module(module):
    shutil.rmtree(BASE, ignore_errors=True)
