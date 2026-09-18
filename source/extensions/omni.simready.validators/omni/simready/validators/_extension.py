from importlib.metadata import entry_points

import omni.ext

from usd_validation_nvidia import PluginManager

# Installed SimReady validation tiers advertise their validator plugin on the
# ``usd_validation_nvidia`` entry-point group under the ``simready.foundation.*``
# namespace (e.g. ``simready.foundation.tier_core:SimReadyPlugin``). Discovering
# them here replaces the retired monolithic ``simready.foundation.core`` package:
# every installed tier is registered, so core + isaac (+ future tiers) all load.
_VALIDATION_GROUP = "usd_validation_nvidia"
_TIER_NAMESPACE = "simready.foundation."


class Extension(omni.ext.IExt):
    """Kit extension that registers every installed SimReady validation tier's rules into the Asset Validator."""

    def on_startup(self) -> None:
        self._plugins = []
        manager = PluginManager()
        for ep in entry_points(group=_VALIDATION_GROUP):
            # ep.value is "<module>:<attr>", e.g. "simready.foundation.tier_core:SimReadyPlugin".
            if not ep.value.startswith(_TIER_NAMESPACE):
                continue
            if manager.is_plugin_loaded(ep.value):
                continue
            plugin = ep.load()()
            plugin.on_startup()
            self._plugins.append(plugin)

    def on_shutdown(self) -> None:
        for plugin in reversed(self._plugins):
            plugin.on_shutdown()
        self._plugins = []
