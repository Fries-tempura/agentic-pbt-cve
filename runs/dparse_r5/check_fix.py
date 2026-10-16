import re, time, warnings, sys
warnings.filterwarnings("ignore")
sys.path.insert(0, "/Users/auderyliu/Documents/NTU/project/agentic-pbt-main/dataset/checkouts/CVE-2022-39280__dparse")
from dparse.parser import Parser

def parse_index_server(cls, line):
    groups = re.split(r"[=\s]+", line.strip(), maxsplit=100)
    if len(groups) >= 2:
        value = groups[1]
        return value if value.endswith("/") else value + "/"
    return None
Parser.parse_index_server = classmethod(parse_index_server)

import tests.test_parse as tp
tp.test_index_server(); tp.test_requirements_package_with_index_server()
t = time.time(); Parser.parse_index_server("--index-url " + "https://" * 5000); print("ok", round(time.time() - t, 4))
