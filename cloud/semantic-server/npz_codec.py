"""Small, pickle-free NPZ encoder with an explicit Deflate level."""

from __future__ import annotations

import asyncio
import io
import zipfile
from collections.abc import Mapping
from concurrent.futures import Executor

import numpy as np


def encode_npz(arrays: Mapping[str, np.ndarray], compression_level: int = 1) -> bytes:
    """Encode named arrays as an ``np.load``-compatible NPZ byte string.

    ``numpy.savez_compressed`` always uses the zipfile default compression level.
    Writing the same ``.npy`` members explicitly lets the service select the faster
    Deflate level 1 while retaining the existing response contract.
    """
    if not 0 <= compression_level <= 9:
        raise ValueError("compression_level must be between 0 and 9")

    output = io.BytesIO()
    with zipfile.ZipFile(
        output,
        mode="w",
        compression=zipfile.ZIP_DEFLATED,
        compresslevel=compression_level,
        allowZip64=True,
    ) as archive:
        for name, array in arrays.items():
            if not name or "/" in name or "\\" in name:
                raise ValueError(f"invalid NPZ member name: {name!r}")
            with archive.open(f"{name}.npy", mode="w", force_zip64=True) as member:
                np.lib.format.write_array(
                    member,
                    np.asanyarray(array),
                    allow_pickle=False,
                )
    return output.getvalue()


async def encode_npz_async(
    arrays: Mapping[str, np.ndarray],
    compression_level: int = 1,
    executor: Executor | None = None,
) -> bytes:
    """Encode an NPZ payload on ``executor`` without blocking the event loop."""
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, encode_npz, arrays, compression_level)
