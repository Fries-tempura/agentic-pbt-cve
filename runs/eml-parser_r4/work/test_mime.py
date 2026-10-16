from hypothesis import given, settings, strategies as st, HealthCheck
import eml_parser.parser as P
import eml_parser.regexes as R

ctype = st.sampled_from(["text/plain", "text/html", "application/octet-stream", "image/png", "message/rfc822", "text/plain; charset=utf-8", "text/plain; charset=bogus", "text/plain; charset=utf-16"])
cte = st.sampled_from(["", "base64", "quoted-printable", "7bit", "8bit", "x-uuencode"])
disp = st.sampled_from(["", "attachment", "inline", 'attachment; filename="a.html"', "attachment; filename*=utf-8''%E4%BD%A0.txt", 'inline; filename="=?utf-8?b?w6k=?="', "attachment; filename="])
body = st.text(alphabet=st.characters(blacklist_categories=("Cs",)), max_size=200)

def leaf():
    return st.builds(lambda ct, e, d, b: (ct, e, d, b), ctype, cte, disp, body)

def render(node, n=[0]):
    if isinstance(node, tuple):
        ct, e, d, b = node
        h = f"Content-Type: {ct}\n"
        if e: h += f"Content-Transfer-Encoding: {e}\n"
        if d: h += f"Content-Disposition: {d}\n"
        if ct == "message/rfc822":
            b = "From: a@b.com\nSubject: inner\n\n" + b
        return h + "\n" + b + "\n"
    n[0] += 1
    bd = f"BOUND{n[0]}"
    out = f'Content-Type: multipart/mixed; boundary="{bd}"\n\n'
    for c in node:
        out += f"--{bd}\n" + render(c)
    out += f"--{bd}--\n"
    return out

tree = st.recursive(leaf(), lambda ch: st.lists(ch, min_size=1, max_size=4), max_leaves=8)

@settings(max_examples=1500, suppress_health_check=list(HealthCheck), deadline=None)
@given(tree, st.booleans(), st.booleans())
def test_mime_no_crash(t, raw, att):
    msg = "From: x@y.com\nTo: z@w.org\nSubject: s\nMIME-Version: 1.0\n" + render(t)
    P.EmlParser(include_raw_body=raw, include_attachment_data=att).decode_email_bytes(msg.encode("utf-8"))

def test_force_tld_global_state():
    orig = R.email_regex
    body = b"From: a@b.com\nSubject: s\n\nwrite to john@doe please\n"
    before = P.EmlParser(include_raw_body=True).decode_email_bytes(body)['body'][0].get('email')
    P.EmlParser(email_force_tld=True)
    after = P.EmlParser(include_raw_body=True).decode_email_bytes(body)['body'][0].get('email')
    R.email_regex = orig
    assert before == after, (before, after)
