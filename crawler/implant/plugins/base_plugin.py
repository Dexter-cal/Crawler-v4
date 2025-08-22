from abc import ABC, abstractmethod
from typing import List, Dict, Any

class BasePlugin(ABC):
    """
    Abstract base class for all Crawler plugins.

    This class defines the standard interface that the core agent uses to discover,
    load, and manage surveillance modules. Each plugin must implement these methods.
    """

    @abstractmethod
    def get_name(self) -> str:
        """
        Return the unique, lowercase name of the plugin (e.g., "keylogger").
        This name is used by the C2 to issue commands.
        """
        pass

    @abstractmethod
    def start(self, args: Dict[str, Any]):
        """
        Start the plugin's data collection process.

        This method should be non-blocking. It's recommended to spawn a new
        thread for any long-running collection tasks. The `args` dictionary
        contains any parameters sent from the C2 with the start command.
        """
        pass

    @abstractmethod
    def stop(self):
        """
        Stop the data collection process and gracefully clean up any resources
        (e.g., threads, file handles).
        """
        pass

    @abstractmethod
    def get_data(self) -> List[Dict[str, Any]]:
        """
        Retrieve any data captured by the plugin since the last time this
        method was called.

        The plugin is responsible for clearing its internal data buffer after
        this call to avoid sending duplicate data.

        Returns:
            A list of data entries. Each entry should be a dictionary
            representing a structured piece of information.
        """
        pass
