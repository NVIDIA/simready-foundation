# SPDX-FileCopyrightText: Copyright (c) 2026 NVIDIA CORPORATION & AFFILIATES. All rights reserved.
# SPDX-License-Identifier: Apache-2.0
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

from pxr import Usd

from .models import RuleConfigurationParam


class RuleInterface(ABC):
    """Abstract base class for asset transformation rules.

    Implementations operate on a source :class:`pxr.Usd.Stage` and may write
    opinions to a destination :class:`pxr.Usd.Stage`. Subclasses should record
    human-readable log messages and any identifiers for stages/layers they
    affect so the manager can produce comprehensive reports.

    Rules may request a stage replacement by returning a stage identifier (file
    path) from :meth:`process_rule`. The manager will open the new stage and
    use it for subsequent rules in the pipeline.
    """

    def __init__(self, source_stage: Usd.Stage, package_root: str, destination_path: str, args: Dict[str, Any]) -> None:
        """Initialize the rule with source/destination stages and execution args.

        Args:
            param source_stage: Input stage providing opinions to read from.
            param package_root: Root directory for output files.
            param destination_path: Relative path for rule outputs.
            param args: Mapping of parameters including keys such as
                ``destination``, ``params``, ...

        Example:

        .. code-block:: python

            >>> from pxr import Usd
            >>> from isaacsim.asset.transformer import RuleInterface
            >>>
            >>> class NoOpRule(RuleInterface):
            ...     def process_rule(self) -> None:
            ...         self.log_operation("noop")
            ...
            >>> src = Usd.Stage.CreateInMemory()
            >>> rule = NoOpRule(src, "/pkg", "", {"destination": "out.usda"})
            >>> rule.process_rule()
            >>> rule.get_operation_log()[-1]
            'noop'
        """
        self.source_stage: Usd.Stage = source_stage
        self.package_root: str = package_root
        self.destination_path: str = destination_path
        self.args: Dict[str, Any] = args or {}
        self._log: List[str] = []
        self._affected_stages: List[str] = []

    @abstractmethod
    def process_rule(self) -> Optional[str]:
        """Execute the rule logic.

        This method must be implemented by subclasses. Implementations should
        emit log messages via :meth:`log_operation` and record any affected
        stage or layer identifiers via :meth:`add_affected_stage`.

        Returns:
            The file path of the stage to be used by subsequent rules. Return
            ``None`` if the current working stage should continue to be used.
            If a path is returned and differs from the current working stage,
            the manager will open the new stage for subsequent rules.
        """
        raise NotImplementedError

    def log_operation(self, message: str) -> None:
        """Append a human-readable message to the operation log.

        Args:
            param message: Message to record in the rule execution log.
        """
        self._log.append(message)

    def get_operation_log(self) -> List[str]:
        """Return the accumulated operation log messages.

        Returns:
            List of log message strings in chronological order.
        """
        return list(self._log)

    def add_affected_stage(self, stage_identifier: str) -> None:
        """Record an identifier for a stage or layer affected by this rule.

        Args:
            param stage_identifier: Logical label, file path, or layer id that
                was created, modified, or otherwise affected by the rule.
        """
        if stage_identifier and stage_identifier not in self._affected_stages:
            self._affected_stages.append(stage_identifier)

    def get_affected_stages(self) -> List[str]:
        """Return identifiers for stages or layers affected by this rule.

        Returns:
            List of unique identifiers provided via :meth:`add_affected_stage`.
        """
        return list(self._affected_stages)

    @abstractmethod
    def get_configuration_parameters(self) -> List[RuleConfigurationParam]:
        """Return the configuration parameters for this rule.

        Returns:
            List of configuration parameters.
        """
        raise NotImplementedError
