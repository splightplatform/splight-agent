from enum import Enum

class DeploymentRestartPolicy(str, Enum):
    ALWAYS = "Always"
    ON_FAILURE = "OnFailure"
    NEVER = "Never"

    def __str__(self):
        return str(self.value)
    

class EngineActionType(str, Enum):
    RUN = "run"
    STOP = "stop"
    RESTART = "restart"