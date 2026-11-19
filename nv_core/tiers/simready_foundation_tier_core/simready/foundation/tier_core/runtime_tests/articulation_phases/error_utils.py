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
"""Hint-prefix helpers shared by articulation phase error messages."""


def asset_fix(message):
    # type: (str) -> str
    """Return *message* prefixed with 'Asset fix: '."""
    return "Asset fix: " + message


def engine_note(message):
    # type: (str) -> str
    """Return *message* prefixed with 'Engine note: '."""
    return "Engine note: " + message


def note_secondary_error(primary, message):
    """Attach an optional note without replacing any original failure.

    Native exceptions and supported older Python runtimes may not provide
    ``add_note``. A lazy message callable also keeps broken secondary string
    formatting inside this fail-soft boundary. This helper never changes
    verdicts, control state, cleanup requirements or the original exception.
    """
    try:
        note = getattr(primary, "add_note", None)
        if callable(note):
            text = message() if callable(message) else message
            if isinstance(text, str):
                note(text[:4096])
    except BaseException:
        pass  # Even diagnostic cancellation must not replace the first cause.


def record_required_cleanup_failure(ctx, reason, primary=None):
    """Retire an uncertain native context without masking its first cause."""
    try:
        session = getattr(ctx, "_engine_session", None)
        record = getattr(session, "record_required_cleanup_failure", None)
        if callable(record):
            record(reason)
    except BaseException as error:
        if primary is not None:
            note_secondary_error(
                primary,
                lambda error=error: f"Required-cleanup retirement diagnostic also failed: {type(error).__name__}",
            )
