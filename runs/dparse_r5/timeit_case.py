import sys, time, warnings
warnings.filterwarnings("ignore")
from dparse.parser import Parser
unit, n = sys.argv[1], int(sys.argv[2])
s = "-i https://" + unit * n
t = time.time(); Parser.parse_index_server(s); print(repr(unit), n, round(time.time() - t, 3), flush=True)
