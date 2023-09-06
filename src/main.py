from splight_agent.orchestrator import Orchestrator

if __name__ == "__main__":
    orchestrator = Orchestrator()
    orchestrator.check_settings()
    orchestrator.start()
