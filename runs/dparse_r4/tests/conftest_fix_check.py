import re, time
from dparse import parser, parse, filetypes
def fixed(cls, line):
    g = re.split(r"[=\s]+", line.strip(), maxsplit=100)
    return (g[1] if g[1].endswith('/') else g[1] + '/') if len(g) >= 2 else None
parser.Parser.parse_index_server = classmethod(fixed)
t = time.perf_counter(); parse("-i https://" + "a.1"*1000 + "\nx==1", file_type=filetypes.requirements_txt); print("fast:", time.perf_counter()-t)
import test_dparse_parser as T
T.test_index_server(); T.test_pinned_requirements_roundtrip(); print("index_server property OK with fix")
