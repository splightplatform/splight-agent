import signal

from splight_agent.orchestrator import Orchestrator

if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.check_settings()

    for signal_name in (
        signal.SIGABRT,
        signal.SIGINT,
        signal.SIGTERM,
        signal.SIGILL,
        signal.SIGSEGV,
    ):
        signal.signal(signal_name, orchestrator.kill)

    orchestrator.start()
