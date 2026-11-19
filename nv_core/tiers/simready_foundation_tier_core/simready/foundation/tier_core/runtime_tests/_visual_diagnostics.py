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
"""Best-effort presentation only; required captures and measurements stay fatal."""

import sys
from contextlib import contextmanager

from simready.evaluate.core.output_layout import UnsafeEvidencePathError


def _optional_encoding_callback(ctx, operation, name, critical_failures):
    def call(*args, **kwargs):
        try:
            return operation(*args, **kwargs)
        except BaseException as error:
            if (
                not isinstance(error, Exception)
                or isinstance(error, UnsafeEvidencePathError)
                or getattr(sys, "_simready_evaluate_kit_engine_retired", False)
            ):
                critical_failures.append(error)
                raise
            warnings = getattr(ctx, "_warnings", None)
            if isinstance(warnings, list):
                message = f"Optional video diagnostic {name} unavailable ({type(error).__name__})."
                if message not in warnings:
                    list.append(warnings, message)
            return None

    return call


@contextmanager
def _encoding_diagnostics(ctx):
    """Scope diagnostic callback isolation without changing engine calls or media validation."""
    attributes = getattr(ctx, "__dict__", None)
    critical_failures = []
    if not isinstance(attributes, dict):
        yield critical_failures
        return
    missing = object()
    saved = []
    try:
        for name in ("warn", "_refresh_timing_metrics"):
            operation = getattr(ctx, name, None)
            if callable(operation):
                saved.append((name, attributes.get(name, missing)))
                setattr(ctx, name, _optional_encoding_callback(ctx, operation, name, critical_failures))
        yield critical_failures
    finally:
        for name, previous in reversed(saved):
            if previous is missing:
                if name in attributes:
                    delattr(ctx, name)
            else:
                setattr(ctx, name, previous)


def visual_warning(ctx, message):
    """A warning transport failure must not replace a measured verdict."""
    try:
        ctx.warn(message)
    except Exception:
        pass


def encode_visual_video(ctx, frames, **options):
    """Isolate only presentation callbacks, including on older supported runtimes.

    RunContext retains encoding and media ownership. Unknown engine
    failures, unsafe paths and cancellation remain required execution errors.
    """
    with _encoding_diagnostics(ctx) as critical_failures:
        result = ctx.encode_video(frames, **options)
        # A newer runtime can also isolate diagnostic exceptions internally.
        # It must not hide a required failure observed by the tier's callback.
        if critical_failures:
            raise critical_failures[0]
        return result
