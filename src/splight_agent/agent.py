import signal

from splight_agent.orchestrator import Orchestrator

SIGNALS_TO_HANDLE = (
    signal.SIGABRT,
    signal.SIGINT,
    signal.SIGTERM,
    signal.SIGILL,
    signal.SIGSEGV,
)

def run():
    orchestrator = Orchestrator()

    for signal_name in SIGNALS_TO_HANDLE:
        signal.signal(signal_name, orchestrator.kill)

    orchestrator.start()