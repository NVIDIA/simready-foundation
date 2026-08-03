import omni.ext

from usd_validation_nvidia import PluginManager
from simready.foundation.core import SimReadyPlugin


class Extension(omni.ext.IExt):
    """Kit extension that registers SimReady Foundation validation rules into the Asset Validator."""

    def on_startup(self) -> None:
        self._plugin = None
        if not PluginManager().is_plugin_loaded("simready.foundation.core:SimReadyPlugin"):
            self._plugin = SimReadyPlugin()
            self._plugin.on_startup()

    def on_shutdown(self) -> None:
        if self._plugin is not None:
            self._plugin.on_shutdown()
