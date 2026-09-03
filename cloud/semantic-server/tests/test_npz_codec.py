import asyncio
import io
import pathlib
import sys
import threading
import unittest
import zipfile
from concurrent.futures import ThreadPoolExecutor
from unittest import mock

import numpy as np


SERVER_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from npz_codec import encode_npz, encode_npz_async  # noqa: E402


class EncodeNpzTest(unittest.TestCase):
    def test_named_arrays_round_trip_through_numpy_load(self):
        expected = {
            "mask": np.arange(12, dtype=np.uint8).reshape(3, 4),
            "conf": np.full((3, 4), 127, dtype=np.uint8),
        }

        payload = encode_npz(expected, compression_level=1)

        with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
            self.assertEqual(archive.files, ["mask", "conf"])
            for name, array in expected.items():
                np.testing.assert_array_equal(archive[name], array)

        with zipfile.ZipFile(io.BytesIO(payload)) as archive:
            self.assertTrue(all(item.compress_type == zipfile.ZIP_DEFLATED
                                for item in archive.infolist()))

    def test_arr_0_preserves_positional_savez_contract(self):
        expected = np.arange(24, dtype=np.uint8).reshape(2, 3, 4)

        payload = encode_npz({"arr_0": expected}, compression_level=1)

        with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
            self.assertEqual(archive.files, ["arr_0"])
            np.testing.assert_array_equal(archive["arr_0"], expected)

    def test_rejects_invalid_compression_level(self):
        with self.assertRaises(ValueError):
            encode_npz({"mask": np.zeros(1, dtype=np.uint8)}, compression_level=10)

    def test_rejects_object_arrays_instead_of_pickling(self):
        with self.assertRaises(ValueError):
            encode_npz({"objects": np.array([object()], dtype=object)})

    def test_async_encoder_runs_on_the_supplied_pool(self):
        worker_threads = []
        original = encode_npz

        def record_thread(arrays, compression_level):
            worker_threads.append(threading.current_thread().name)
            return original(arrays, compression_level)

        async def run():
            with ThreadPoolExecutor(max_workers=1,
                                    thread_name_prefix="test-npz-compress") as executor:
                with mock.patch("npz_codec.encode_npz", side_effect=record_thread):
                    return await encode_npz_async(
                        {"mask": np.zeros((2, 2), dtype=np.uint8)},
                        compression_level=1,
                        executor=executor,
                    )

        payload = asyncio.run(run())
        with np.load(io.BytesIO(payload), allow_pickle=False) as archive:
            self.assertEqual(archive.files, ["mask"])
        self.assertEqual(len(worker_threads), 1)
        self.assertTrue(worker_threads[0].startswith("test-npz-compress"))


if __name__ == "__main__":
    unittest.main()
