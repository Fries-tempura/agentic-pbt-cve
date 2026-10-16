import signal, time, warnings
warnings.simplefilter("ignore")
from hypothesis import given, settings, strategies as st, HealthCheck, Phase
from dparse.parser import Parser
class Slow(Exception): pass
def h(*a): raise Slow()
signal.signal(signal.SIGALRM, h)
@settings(deadline=None, max_examples=300, suppress_health_check=list(HealthCheck), phases=[Phase.generate])
@given(st.text(alphabet="a1-.", min_size=1, max_size=4), st.integers(10, 40), st.sampled_from(["", "!", " ", ".", "-"]))
def t(chunk, reps, end):
    line = "-i https://" + chunk * reps + end
    signal.alarm(2)
    try:
        Parser.parse_index_server(line)
    except Slow:
        print("SLOW:", repr(chunk), reps, repr(end), flush=True); raise
    finally:
        signal.alarm(0)
t()
