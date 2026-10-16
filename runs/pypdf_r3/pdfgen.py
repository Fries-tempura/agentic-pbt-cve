def build_pdf(objects, trailer_extra=b"", include_root=True, size=None, first_index=0, eol=b" \n"):
    """objects: list of bytes bodies for objects 1..n. Returns valid PDF bytes with correct xref."""
    out = bytearray(b"%PDF-1.7\n")
    offsets = []
    for i, body in enumerate(objects, start=1):
        offsets.append(len(out))
        out += b"%d 0 obj\n" % i + body + b"\nendobj\n"
    xref_pos = len(out)
    n = len(objects) + 1
    out += b"xref\n%d %d\n" % (first_index, n)
    out += b"0000000000 65535 f" + eol
    for off in offsets:
        out += b"%010d 00000 n" % off + eol
    if size is None:
        size = n
    out += b"trailer\n<< /Size %d " % size
    if include_root:
        out += b"/Root 1 0 R "
    out += trailer_extra + b">>\nstartxref\n%d\n%%%%EOF\n" % xref_pos
    return bytes(out)
