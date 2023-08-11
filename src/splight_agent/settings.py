import os
from typing import Any, Dict, Tuple

import yaml
from pydantic import BaseSettings, Extra, root_validator
from pydantic.env_settings import SettingsSourceCallable

SPLIGHT_HOME = os.path.join(os.getenv("HOME"), ".splight")
API_POLL_INTERVAL = 15

class Singleton:
    def __new__(cls, *args, **kw):
        if not hasattr(cls, "_instance"):
            org = super(Singleton, cls)
            cls._instance = org.__new__(cls, *args, **kw)
        return cls._instance


def yml_config_setting(settings: BaseSettings) -> Dict[str, Any]:
    config = {}
    config_file = os.path.join(SPLIGHT_HOME, "agent_config")
    if os.path.exists(config_file):
        with open(config_file) as f:
            config = yaml.safe_load(f)
    return config


class SplightSettings(BaseSettings, Singleton):
    SPLIGHT_ACCESS_ID: str = ""
    SPLIGHT_SECRET_KEY: str = ""
    SPLIGHT_PLATFORM_API_HOST: str = "https://api.splight-ai.com"
    COMPUTE_NODE_ID: str = ""
    WORKSPACE_NAME: str = ""
    ECR_REPOSITORY: str = ""
    NAMESPACE: str = ""

    def configure(self, **params: Dict):
        self.parse_obj(params)

    class Config:
        extra = Extra.ignore

        @classmethod
        def customise_sources(
            cls,
            init_settings: SettingsSourceCallable,
            env_settings: SettingsSourceCallable,
            file_secret_settings: SettingsSourceCallable,
        ) -> Tuple[SettingsSourceCallable, ...]:
            return init_settings, yml_config_setting, env_settings
        
    def save(self):
        config_file = os.path.join(SPLIGHT_HOME, "agent_config")
        with open(config_file, "w") as f:
            yaml.dump(self.dict(), f)

settings = SplightSettings()
