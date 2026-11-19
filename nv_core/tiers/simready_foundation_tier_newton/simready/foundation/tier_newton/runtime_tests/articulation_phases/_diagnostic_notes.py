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


def note_secondary_error(primary, message):
    """Never replace a required failure with its optional note operation.

    Python 3.10 and native errors may not expose a callable ``add_note``.
    Message callables keep secondary formatting within the same boundary.
    """
    try:
        note = getattr(primary, "add_note", None)
        if callable(note):
            text = message() if callable(message) else message
            if isinstance(text, str):
                note(text[:4096])
    except BaseException:
        pass


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
