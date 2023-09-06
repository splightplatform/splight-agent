from splight_agent.orchestrator import Orchestrator
import signal


if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.check_settings()

    for signal in (signal.SIGABRT, signal.SIGINT, signal.SIGTERM, signal.SIGKILL):
        signal.signal(signal, orchestrator.kill)

    orchestrator.start()
