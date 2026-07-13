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

import logging
from typing import Dict, Optional

import numpy  # used to represent Vectors, Matrices, and Colors

try:
    from omni.mdl import neuraylib, pymdl, pymdlsdk
except ImportError:
    neuraylib = None
    pymdl = None
    pymdlsdk = None

from pxr import Gf, Sdf

logger = logging.getLogger(__name__)

# --------------------------------------------------------------------------------------------------
# USD and misc utilities, from omni.mdl.usd_converter
# --------------------------------------------------------------------------------------------------

MdlIValueKindToUSD = {}
MdlITypeKindToUSD = {}

if pymdlsdk is not None:
    MdlIValueKindToUSD = {
        pymdlsdk.IValue.Kind.VK_BOOL: Sdf.ValueTypeNames.Bool,
        pymdlsdk.IValue.Kind.VK_INT: Sdf.ValueTypeNames.Int,
        pymdlsdk.IValue.Kind.VK_ENUM: Sdf.ValueTypeNames.Int,
        pymdlsdk.IValue.Kind.VK_FLOAT: Sdf.ValueTypeNames.Float,
        pymdlsdk.IValue.Kind.VK_DOUBLE: Sdf.ValueTypeNames.Double,
        pymdlsdk.IValue.Kind.VK_STRING: Sdf.ValueTypeNames.String,
        pymdlsdk.IValue.Kind.VK_COLOR: Sdf.ValueTypeNames.Color3f,
        pymdlsdk.IValue.Kind.VK_STRUCT: Sdf.ValueTypeNames.Token,
        pymdlsdk.IValue.Kind.VK_TEXTURE: Sdf.ValueTypeNames.Asset,
        pymdlsdk.IValue.Kind.VK_LIGHT_PROFILE: Sdf.ValueTypeNames.Asset,
        pymdlsdk.IValue.Kind.VK_BSDF_MEASUREMENT: Sdf.ValueTypeNames.Asset,
    }
    MdlITypeKindToUSD = {
        pymdlsdk.IType.Kind.TK_BOOL: Sdf.ValueTypeNames.Bool,
        pymdlsdk.IType.Kind.TK_INT: Sdf.ValueTypeNames.Int,
        pymdlsdk.IType.Kind.TK_ENUM: Sdf.ValueTypeNames.Int,
        pymdlsdk.IType.Kind.TK_FLOAT: Sdf.ValueTypeNames.Float,
        pymdlsdk.IType.Kind.TK_DOUBLE: Sdf.ValueTypeNames.Double,
        pymdlsdk.IType.Kind.TK_STRING: Sdf.ValueTypeNames.String,
        pymdlsdk.IType.Kind.TK_COLOR: Sdf.ValueTypeNames.Color3f,
        pymdlsdk.IType.Kind.TK_STRUCT: Sdf.ValueTypeNames.Token,
        pymdlsdk.IType.Kind.TK_TEXTURE: Sdf.ValueTypeNames.Asset,
        pymdlsdk.IType.Kind.TK_LIGHT_PROFILE: Sdf.ValueTypeNames.Asset,
        pymdlsdk.IType.Kind.TK_BSDF_MEASUREMENT: Sdf.ValueTypeNames.Asset,
    }


def python_vector_to_usd_type(dtype, size):
    if dtype == numpy.int32 or dtype == bool:
        return {2: Sdf.ValueTypeNames.Int2, 3: Sdf.ValueTypeNames.Int3, 4: Sdf.ValueTypeNames.Int4}.get(size)
    elif dtype == numpy.float32:
        return {2: Sdf.ValueTypeNames.Float2, 3: Sdf.ValueTypeNames.Float3, 4: Sdf.ValueTypeNames.Float4}.get(size)
    elif dtype == numpy.float64:
        return {2: Sdf.ValueTypeNames.Double2, 3: Sdf.ValueTypeNames.Double3, 4: Sdf.ValueTypeNames.Double4}.get(size)
    return None


def python_vector_to_usd_value(value):
    dtype = value.dtype
    size = value.size
    out = None
    if dtype == numpy.int32 or dtype == bool:
        if size == 2:
            out = Gf.Vec2i(0)
        elif size == 3:
            out = Gf.Vec3i(0)
        elif size == 4:
            out = Gf.Vec4i(0)
        if out is not None:
            for i in range(size):
                out[i] = int(value[i][0])
    elif dtype == numpy.float32:
        if size == 2:
            out = Gf.Vec2f(0)
        elif size == 3:
            out = Gf.Vec3f(0)
        elif size == 4:
            out = Gf.Vec4f(0)
        if out is not None:
            for i in range(size):
                out[i] = float(value[i][0])
    elif dtype == numpy.float64:
        if size == 2:
            out = Gf.Vec2d(0)
        elif size == 3:
            out = Gf.Vec3d(0)
        elif size == 4:
            out = Gf.Vec4d(0)
        if out is not None:
            for i in range(size):
                out[i] = numpy.float64(value[i][0])
    return out


def custom_data_from_python_vector(value):
    dtype = value.dtype
    if dtype == bool:
        size = value.size
        return {"mdl": {"type": "bool{}".format(size)}}
    else:
        return {}


def python_matrix_to_usd_type(dtype, nrow, ncol):
    #     numpyType   Column Row           OutType
    m = {
        "float32": {
            2: {2: Sdf.ValueTypeNames.Matrix2d, 3: Sdf.ValueTypeNames.Float3Array, 4: Sdf.ValueTypeNames.Float4Array},
            3: {2: Sdf.ValueTypeNames.Float2Array, 3: Sdf.ValueTypeNames.Matrix3d, 4: Sdf.ValueTypeNames.Float4Array},
            4: {2: Sdf.ValueTypeNames.Float2Array, 3: Sdf.ValueTypeNames.Float3Array, 4: Sdf.ValueTypeNames.Matrix4d},
        },
        "float64": {
            2: {2: Sdf.ValueTypeNames.Matrix2d, 3: Sdf.ValueTypeNames.Double3Array, 4: Sdf.ValueTypeNames.Double4Array},
            3: {2: Sdf.ValueTypeNames.Double2Array, 3: Sdf.ValueTypeNames.Matrix3d, 4: Sdf.ValueTypeNames.Double4Array},
            4: {2: Sdf.ValueTypeNames.Double2Array, 3: Sdf.ValueTypeNames.Double3Array, 4: Sdf.ValueTypeNames.Matrix4d},
        },
    }
    return m[dtype.name][ncol][nrow]


def python_matrix_to_usd_value(value):
    dtype = value.dtype
    nrow = value.shape[0]
    ncol = value.shape[1]
    out = None
    if dtype == numpy.float32:
        if ncol == 2:
            if nrow == 2:
                out = Gf.Matrix2d(0)
                out.SetColumn(0, Gf.Vec2d(float(value[0][0]), float(value[0][1])))
                out.SetColumn(1, Gf.Vec2d(float(value[1][0]), float(value[1][1])))
            elif nrow == 3:
                out = [
                    Gf.Vec3f(float(value[0][0]), float(value[1][0]), float(value[2][0])),
                    Gf.Vec3f(float(value[0][1]), float(value[1][1]), float(value[2][1])),
                ]
            elif nrow == 4:
                out = [
                    Gf.Vec4f(float(value[0][0]), float(value[1][0]), float(value[2][0]), float(value[3][0])),
                    Gf.Vec4f(float(value[0][1]), float(value[1][1]), float(value[2][1]), float(value[3][1])),
                ]
        elif ncol == 3:
            if nrow == 2:
                out = [
                    Gf.Vec2f(float(value[0][0]), float(value[1][0])),
                    Gf.Vec2f(float(value[0][1]), float(value[1][1])),
                    Gf.Vec2f(float(value[0][2]), float(value[1][2])),
                ]
            elif nrow == 3:
                out = Gf.Matrix3d(0)
                out.SetColumn(0, Gf.Vec3d(float(value[0][0]), float(value[0][1]), float(value[0][2])))
                out.SetColumn(1, Gf.Vec3d(float(value[1][0]), float(value[1][1]), float(value[1][2])))
                out.SetColumn(2, Gf.Vec3d(float(value[2][0]), float(value[2][1]), float(value[2][2])))
            elif nrow == 4:
                out = [
                    Gf.Vec4f(float(value[0][0]), float(value[1][0]), float(value[2][0]), float(value[3][0])),
                    Gf.Vec4f(float(value[0][1]), float(value[1][1]), float(value[2][1]), float(value[3][1])),
                    Gf.Vec4f(float(value[0][2]), float(value[1][2]), float(value[2][2]), float(value[3][2])),
                ]
        elif ncol == 4:
            if nrow == 2:
                out = [
                    Gf.Vec2f(float(value[0][0]), float(value[1][0])),
                    Gf.Vec2f(float(value[0][1]), float(value[1][1])),
                    Gf.Vec2f(float(value[0][2]), float(value[1][2])),
                    Gf.Vec2f(float(value[0][3]), float(value[1][3])),
                ]
            elif nrow == 3:
                out = [
                    Gf.Vec3f(float(value[0][0]), float(value[1][0]), float(value[2][0])),
                    Gf.Vec3f(float(value[0][1]), float(value[1][1]), float(value[2][1])),
                    Gf.Vec3f(float(value[0][2]), float(value[1][2]), float(value[2][2])),
                    Gf.Vec3f(float(value[0][3]), float(value[1][3]), float(value[2][3])),
                ]
            elif nrow == 4:
                out = Gf.Matrix4d(0)
                out.SetColumn(
                    0, Gf.Vec4d(float(value[0][0]), float(value[0][1]), float(value[0][2]), float(value[0][3]))
                )
                out.SetColumn(
                    1, Gf.Vec4d(float(value[1][0]), float(value[1][1]), float(value[1][2]), float(value[1][3]))
                )
                out.SetColumn(
                    2, Gf.Vec4d(float(value[2][0]), float(value[2][1]), float(value[2][2]), float(value[2][3]))
                )
                out.SetColumn(
                    3, Gf.Vec4d(float(value[3][0]), float(value[3][1]), float(value[3][2]), float(value[3][3]))
                )
    elif dtype == numpy.float64:
        if ncol == 2:
            if nrow == 2:
                out = Gf.Matrix2d(0)
                out.SetColumn(0, Gf.Vec2d(float(value[0][0]), float(value[0][1])))
                out.SetColumn(1, Gf.Vec2d(float(value[1][0]), float(value[1][1])))
            elif nrow == 3:
                out = [
                    Gf.Vec3d(float(value[0][0]), float(value[1][0]), float(value[2][0])),
                    Gf.Vec3d(float(value[0][1]), float(value[1][1]), float(value[2][1])),
                ]
            elif nrow == 4:
                out = [
                    Gf.Vec4d(float(value[0][0]), float(value[1][0]), float(value[2][0]), float(value[3][0])),
                    Gf.Vec4d(float(value[0][1]), float(value[1][1]), float(value[2][1]), float(value[3][1])),
                ]
        elif ncol == 3:
            if nrow == 2:
                out = [
                    Gf.Vec2d(float(value[0][0]), float(value[1][0])),
                    Gf.Vec2d(float(value[0][1]), float(value[1][1])),
                    Gf.Vec2d(float(value[0][2]), float(value[1][2])),
                ]
            elif nrow == 3:
                out = Gf.Matrix3d(0)
                out.SetColumn(0, Gf.Vec3d(float(value[0][0]), float(value[0][1]), float(value[0][2])))
                out.SetColumn(1, Gf.Vec3d(float(value[1][0]), float(value[1][1]), float(value[1][2])))
                out.SetColumn(2, Gf.Vec3d(float(value[2][0]), float(value[2][1]), float(value[2][2])))
            elif nrow == 4:
                out = [
                    Gf.Vec4d(float(value[0][0]), float(value[1][0]), float(value[2][0]), float(value[3][0])),
                    Gf.Vec4d(float(value[0][1]), float(value[1][1]), float(value[2][1]), float(value[3][1])),
                    Gf.Vec4d(float(value[0][2]), float(value[1][2]), float(value[2][2]), float(value[3][2])),
                ]
        elif ncol == 4:
            if nrow == 2:
                out = [
                    Gf.Vec2d(float(value[0][0]), float(value[1][0])),
                    Gf.Vec2d(float(value[0][1]), float(value[1][1])),
                    Gf.Vec2d(float(value[0][2]), float(value[1][2])),
                    Gf.Vec2d(float(value[0][3]), float(value[1][3])),
                ]
            elif nrow == 3:
                out = [
                    Gf.Vec3d(float(value[0][0]), float(value[1][0]), float(value[2][0])),
                    Gf.Vec3d(float(value[0][1]), float(value[1][1]), float(value[2][1])),
                    Gf.Vec3d(float(value[0][2]), float(value[1][2]), float(value[2][2])),
                    Gf.Vec3d(float(value[0][3]), float(value[1][3]), float(value[2][3])),
                ]
            elif nrow == 4:
                out = Gf.Matrix4d(0)
                out.SetColumn(
                    0, Gf.Vec4d(float(value[0][0]), float(value[0][1]), float(value[0][2]), float(value[0][3]))
                )
                out.SetColumn(
                    1, Gf.Vec4d(float(value[1][0]), float(value[1][1]), float(value[1][2]), float(value[1][3]))
                )
                out.SetColumn(
                    2, Gf.Vec4d(float(value[2][0]), float(value[2][1]), float(value[2][2]), float(value[2][3]))
                )
                out.SetColumn(
                    3, Gf.Vec4d(float(value[3][0]), float(value[3][1]), float(value[3][2]), float(value[3][3]))
                )
    return out


def python_array_to_usd_type(value):
    array_simple_conversion = {
        bool: Sdf.ValueTypeNames.BoolArray,
        int: Sdf.ValueTypeNames.IntArray,
        # TODO: enum?
        # AddArrayOfSimpleConversion(mi::neuraylib::IType::TK_ENUM, SdfValueTypeNames->IntArray);
        float: Sdf.ValueTypeNames.FloatArray,
        # TODO: double ?
        # AddArrayOfSimpleConversion(mi::neuraylib::IType::TK_DOUBLE, SdfValueTypeNames->DoubleArray);
        str: Sdf.ValueTypeNames.StringArray,
        pymdlsdk.IType.Kind.TK_COLOR: Sdf.ValueTypeNames.Color3fArray,
        # TODO: AddArrayOfSimpleConversion(mi::neuraylib::IType::TK_STRUCT, SdfValueTypeNames->TokenArray);
        # TODO: AddArrayOfSimpleConversion(mi::neuraylib::IType::TK_TEXTURE, SdfValueTypeNames->AssetArray);
    }

    array_of_vector_conversion = {
        numpy.bool_: {
            2: Sdf.ValueTypeNames.Int2Array,
            3: Sdf.ValueTypeNames.Int3Array,
            4: Sdf.ValueTypeNames.Int4Array,
        },
        numpy.int32: {
            2: Sdf.ValueTypeNames.Int2Array,
            3: Sdf.ValueTypeNames.Int3Array,
            4: Sdf.ValueTypeNames.Int4Array,
        },
        numpy.float32: {
            2: Sdf.ValueTypeNames.Float2Array,
            3: Sdf.ValueTypeNames.Float3Array,
            4: Sdf.ValueTypeNames.Float4Array,
        },
        numpy.float64: {
            2: Sdf.ValueTypeNames.Double2Array,
            3: Sdf.ValueTypeNames.Double3Array,
            4: Sdf.ValueTypeNames.Double4Array,
        },
    }

    # // Array of matrix
    #     numpyType   Column Row           OutType
    array_of_matrix = {
        numpy.float32: {
            2: {
                2: Sdf.ValueTypeNames.Matrix2dArray,
                3: Sdf.ValueTypeNames.FloatArray,
                4: Sdf.ValueTypeNames.FloatArray,
            },
            3: {
                2: Sdf.ValueTypeNames.FloatArray,
                3: Sdf.ValueTypeNames.Matrix3dArray,
                4: Sdf.ValueTypeNames.FloatArray,
            },
            4: {
                2: Sdf.ValueTypeNames.FloatArray,
                3: Sdf.ValueTypeNames.FloatArray,
                4: Sdf.ValueTypeNames.Matrix4dArray,
            },
        },
        numpy.float64: {
            2: {
                2: Sdf.ValueTypeNames.Matrix2dArray,
                3: Sdf.ValueTypeNames.DoubleArray,
                4: Sdf.ValueTypeNames.DoubleArray,
            },
            3: {
                2: Sdf.ValueTypeNames.DoubleArray,
                3: Sdf.ValueTypeNames.Matrix3dArray,
                4: Sdf.ValueTypeNames.DoubleArray,
            },
            4: {
                2: Sdf.ValueTypeNames.DoubleArray,
                3: Sdf.ValueTypeNames.DoubleArray,
                4: Sdf.ValueTypeNames.Matrix4dArray,
            },
        },
    }

    dtype = type(value[0])
    if dtype in array_simple_conversion:
        return array_simple_conversion[dtype]
    elif dtype == numpy.ndarray:
        shape = value[0].shape
        # Array
        if len(shape) > 1 and shape[1] > 1:
            # Array of matrices
            elemtype = type(value[0][0][0])
            if (
                elemtype in array_of_matrix
                and shape[1] in array_of_matrix[elemtype]
                and shape[0] in array_of_matrix[elemtype][shape[1]]
            ):
                return array_of_matrix[elemtype][shape[1]][shape[0]]
        elif isinstance(value[0][0], numpy.ndarray):
            # Array of vectors
            etype = type(value[0][0][0])
            size = len(value[0])
            if etype in array_of_vector_conversion:
                if size in array_of_vector_conversion[etype]:
                    return array_of_vector_conversion[etype][size]
            else:
                print("Array of vector type not supported for type/size: {}/{}".format(etype, size))
        elif len(value[0]) == 3:
            # Assume this is a color
            return array_simple_conversion[pymdlsdk.IType.Kind.TK_COLOR]
        else:
            print("Array type not supported for type/shape: {}/{}".format(dtype, shape))
    else:
        print("Type not supported for type: {}".format(dtype))


def mdl_type_to_usd_type(val: pymdl.ArgumentConstant):
    if not val:
        return None
    kind = val.type.kind
    if kind in MdlITypeKindToUSD:
        return MdlITypeKindToUSD[kind]
    else:
        # A bit more work is required to derive the type
        hasvalue = hasattr(val, "value") and val.value is not None
        hasdtype = hasvalue and hasattr(val.value, "dtype") and val.value.dtype is not None
        if hasvalue and hasdtype:
            if kind == pymdlsdk.IType.Kind.TK_VECTOR:
                return python_vector_to_usd_type(val.value.dtype, val.value.size)
            elif kind == pymdlsdk.IType.Kind.TK_MATRIX:
                return python_matrix_to_usd_type(val.value.dtype, val.value.shape[0], val.value.shape[1])
            elif kind == pymdlsdk.IType.Kind.TK_ARRAY and val.value:
                return python_array_to_usd_type(val.value)
        elif hasvalue:
            return python_array_to_usd_type(val.value)

    return None


def is_mdl_helper_available() -> bool:
    return neuraylib is not None

def get_mdl_module_parameter_descs(module_name: str, function: str) -> Optional[Dict[str, Sdf.ValueTypeName]]:
    # acquire neuray instance from OV
    if not is_mdl_helper_available():
        return None

    ov_neuraylib = neuraylib.get_neuraylib()
    ov_neuraylib_handle = ov_neuraylib.getNeurayAPI()

    # feed the neuray instance into the python binding
    neuray: pymdlsdk.INeuray = pymdlsdk.attach_ineuray(ov_neuraylib_handle)
    if neuray.get_status() != pymdlsdk.INeuray.Status.STARTED:
        logger.warning("Cannot attach to ov neuraylib")
        return None

    # we need to load modules to OV using the omni.mdl.neuraylib
    # on the c++ side this is async, here it is blocking!
    module = ov_neuraylib.createMdlModule(module_name)
    if not module.valid():
        logger.warning(f"Failed creating shell for module {module_name}")
        return None

    # after the module is loaded we create a new transaction that can see the loaded module
    transation_read_handle = ov_neuraylib.createReadingTransaction(module.dbScopeName)
    transaction: pymdlsdk.ITransaction = pymdlsdk.attach_itransaction(transation_read_handle)

    names_to_types: Dict[str, Sdf.ValueTypeName] = {}

    try:
        module_desc = pymdl.Module._fetchFromDb(transaction, module.dbName)
        if not module_desc:
            logger.warning(f"Failed fetching module {module_name}")
            return None

        func_def = module_desc.functions.get(function)
        if not func_def:
            logger.warning(f"Cannot find {function} in {module_name}")
            return None

        # Materials are expected to have only one functions overload
        func_def = func_def[0]

        for param_name, param_desc in func_def.parameters.items():
            try:
                # Ignore function calls for now, only check constants
                if isinstance(param_desc, pymdl.ArgumentConstant):
                    names_to_types[param_name] = mdl_type_to_usd_type(param_desc)

            except Exception as e:
                logger.warning(f"Cannot parse {param_name}: {param_desc.type.kind} : {e}")

    finally:
        ov_neuraylib.destroyMdlModule(module)

        # since we have been reading only, abort
        transaction.abort()
        transaction = None

    return names_to_types
