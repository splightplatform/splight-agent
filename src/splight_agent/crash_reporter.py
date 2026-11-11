import time
from threading import Event, Thread

from docker import from_env
from docker.errors import NotFound

from splight_agent.logging import SplightLogger
from splight_agent.models import ComputeNode

logger = SplightLogger()


class CrashReporter:
    """
    The crash reporter logs the exit code and the last output lines of
    components whose container crashed
    """

    def __init__(self, compute_node: ComputeNode) -> None:
        self._compute_node = compute_node
        self._client = from_env()
        self._stop = Event()
        self._thread = Thread(target=self._run_event_loop, daemon=True)

    @property
    def _filters(self) -> dict:
        return {
            "label": [f"AgentID={self._compute_node.id}", "ComponentID"],
            "event": ["die"],
        }

    def _process_die_event(self, event: dict) -> None:
        attributes = event["Actor"]["Attributes"]
        exit_code = attributes["exitCode"]
        component_id = attributes["ComponentID"]
        # 143: SIGTERM stop. 137 without OOM: SIGKILL after the stop timeout
        if exit_code in ("0", "143"):
            return
        try:
            container = self._client.containers.get(event["Actor"]["ID"])
        except NotFound:
            return
        state = container.attrs["State"]
        oom_killed = state["OOMKilled"]
        if exit_code == "137" and not oom_killed:
            return
        tail = container.logs(tail=100).decode("utf-8", errors="replace")
        logger.error(
            f"Component {component_id} exited with code {exit_code} "
            f"(oom_killed={oom_killed}, "
            f"restart_count={container.attrs['RestartCount']}, "
            f"finished_at={state['FinishedAt']})\n"
            f"Last 100 log lines:\n{tail}",
            extra={
                "tags": ["component_crash", f"component_id:{component_id}"]
            },
        )

    def _run_event_loop(self) -> None:
        while not self._stop.is_set():
            try:
                for event in self._client.events(
                    decode=True, filters=self._filters
                ):
                    try:
                        self._process_die_event(event)
                    except Exception as e:
                        logger.warning(f"Could not report crash: {e}")
            except Exception as e:
                logger.warning(f"Event stream failed, reconnecting: {e}")
                time.sleep(5)

    def start(self) -> None:
        """
        Launch the crash reporter daemon thread
        """
        self._thread.start()
        logger.info("Crash reporter started")

    def stop(self) -> None:
        """
        Stop the crash reporter daemon thread
        """
        self._stop.set()
        logger.info("Crash reporter stopped")
