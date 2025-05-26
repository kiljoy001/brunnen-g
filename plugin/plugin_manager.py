from abc import ABC, abstractmethod
from enum import Enum
import aiorwlock
import importlib
import json

class PluginStates(Enum):
    """Plugin lifecycle states monitoring availiablity"""
    INACTIVE = "inactive"
    LOADING = "loading"
    ACTIVE = "active"
    STOPPING = "stopping"

class HealthStates(Enum):
    """Plugin health status monitoring performance"""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    FAILED = "failed"
    RECOVERING = "recovering"

class AbstractPlugin(ABC):

    def __init__(self, plugin_name: str):
        self.name = plugin_name
        self.lifecycle = PluginLifecycleFSM()
        self.health = PluginHealthFSM()

    @abstractmethod
    async def initialize(self) -> bool:
        pass

    @abstractmethod
    async def start(self) -> bool:
        pass

    @abstractmethod
    async def process_event(self, event: dict) -> bool:
        pass

    @abstractmethod
    async def get_status(self) -> dict:
        pass
    
    @abstractmethod
    async def stop(self) -> bool:
        pass

class PluginLifecycleFSM():
    """Finite state machine that manages plugin states"""
    async def can_transition(self, new_state: PluginStates) -> bool:
        pass
    async def transition_to(self, new_state: PluginStates) -> bool:
        pass

class PluginHealthFSM():
    """Finite state machine that manages plugin health status"""
    async def report_error(self):
        pass
    async def report_success(self):
        pass
    async def transition_to(self, new_state: HealthStates) -> bool:
        pass

class PluginManager():
    """Manages plugins for application"""
    def __init__(self):
        self.registry = {}
        self._lock = aiorwlock.RWLock()
    
    async def register(self, json_file_path: str) -> bool:
        try:
            with open(json_file_path, 'r') as file:
                config = json.load(file)
            # File Data
            class_path = config["class_path"]
            plugin_name = config["name"]
            module_name, class_name = class_path.rsplit('.', 1)
            # Load python file
            module = importlib.import_module(module_name)

            # Get the class and create instance
            pulgin_class = getattr(module, class_name)
            plugin_instance = pulgin_class(plugin_name)
            # Store it
            self.registry[plugin_name] = plugin_instance
            return True
        except KeyError as e:
            print(f"Mising key: {e}")
            return False
        except Exception as e:
            print(f"exception: {e}")
            return False
    async def unregister(self) -> bool:
        pass
    async def get_ready_state(self, plugin_name: str) -> PluginStates:
        pass
    async def get_plugin_health(self, plugin_name: str) -> HealthStates:
        pass
