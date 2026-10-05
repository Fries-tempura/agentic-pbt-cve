import eml_parser.routing as r

for s in [
    'for a ( from b )',
    'for a ( x from b )',
    'by h for a ( from b )',
]:
    try:
        print(repr(s), '->', r.parserouting(s))
    except Exception as e:
        print(repr(s), '-> EXC', type(e).__name__, e)
