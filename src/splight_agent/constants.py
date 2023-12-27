from enum import Enum


IMAGE_DIRECTORY = "/images"


class EngineActionType(str, Enum):
    RUN = "run"
    STOP = "stop"
    RESTART = "restart"


class DeploymentRestartPolicy(str, Enum):
    ALWAYS = "Always"
    ON_FAILURE = "OnFailure"
    NEVER = "Never"

    def __str__(self):
        return str(self.value)


class DeploymentSize(str, Enum):
    SMALL = "small"
    MEDIUM = "medium"
    LARGE = "large"
    VERY_LARGE = "very_large"

    def __str__(self):
        return self.value
