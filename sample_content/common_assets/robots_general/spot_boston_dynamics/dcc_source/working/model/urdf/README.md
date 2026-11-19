# Spot DCC source notices

`model.urdf` is byte-identical to the file in
[Boston Dynamics' Spot base URDF archive at commit 91ed30607264e795699995d6d7834ba0c8a94d36](https://github.com/boston-dynamics/spot-sdk/blob/91ed30607264e795699995d6d7834ba0c8a94d36/files/spot_base_urdf.zip).
All 13 files in `link_models/` match that archive after CRLF-to-LF normalization;
their only byte differences are line endings. The archive is part of the Spot
SDK repository. File hashes and comparison results are recorded in
[license-audit.json](license-audit.json). This verifies the upstream file match;
it does not assert coverage by a separate Boston Dynamics permission letter.
The full [Boston Dynamics Software Development Kit License](LICENSE.Boston-Dynamics-SDK)
and its copyright notice are included here. These model files are not covered
by this repository's Apache-2.0 license.

## MODIFIED VERSION NOTICE

**The 13 `link_models/*.obj` files are MODIFIED VERSIONS solely because their
line endings differ from the upstream archive.** Mesh content is otherwise
unchanged. `model.urdf` is unchanged.

## Permitted use and redistribution

Under SDK license section 2(c), these model files and their converted or modified
versions are licensed solely for use with products offered for sale by Boston
Dynamics. Software-based simulation or emulation is permitted; use with any
other hardware is strictly prohibited. Recipients must retain the complete SDK
license and all copyright and proprietary notices, keep modified versions
conspicuously marked, and distribute them under the SDK license (sections 2(a)
and 2(e)). This repository's Apache-2.0 license and the dataset's MIT license do
not expand those permissions.

## Names and trademarks

The Spot directory, URDF robot name, dataset manufacturer field, and
source/license attribution use Boston Dynamics and Spot names as factual
identifiers. Review of these files and six geometry views found no Boston
Dynamics logos or promotional/endorsement statements. The OBJ files contain no
texture assets or references. No written trademark approval is
included or claimed. SDK license section 2(d) requires prior written consent
before using Boston Dynamics names or trademarks to endorse or promote products.

This directory also contains `meta-information.json` from the
[URDF Files Dataset](https://github.com/Daniella1/urdf_files_dataset/blob/main/urdf_files/oems/spot_boston_dynamics/spot_base_urdf/meta-information.json).
The dataset's [MIT license](LICENSE.MIT) and copyright notice are included for
its contribution. That MIT license does not replace Boston Dynamics' license
for the original model files.
