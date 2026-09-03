import asyncio
import pathlib
import sys
import unittest


SERVER_DIR = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(SERVER_DIR))

from batch_scheduler import BatchQueue, QueueFull  # noqa: E402


class BatchQueueTest(unittest.IsolatedAsyncioTestCase):
    async def test_opportunistic_collection_preserves_compatibility_buckets(self):
        queue = BatchQueue(3, 0, 8, policy="opportunistic")
        queue.put("a1", ("shape-a", "mask"))
        queue.put("b1", ("shape-b", "mask"))
        queue.put("a2", ("shape-a", "mask"))

        first = await queue.collect()
        second = await queue.collect()

        self.assertEqual([item.payload for item in first], ["a1", "a2"])
        self.assertEqual([item.payload for item in second], ["b1"])

    async def test_opportunistic_collection_does_not_add_event_loop_linger(self):
        queue = BatchQueue(2, 0.2, 8, policy="opportunistic")
        queue.put("first", "key")
        asyncio.get_running_loop().call_soon(queue.put, "later", "key")

        first = await queue.collect()
        await asyncio.sleep(0)
        second = await queue.collect()

        self.assertEqual([item.payload for item in first], ["first"])
        self.assertEqual([item.payload for item in second], ["later"])

    async def test_adaptive_idle_request_does_not_pay_timer(self):
        queue = BatchQueue(2, 0.2, 8, policy="adaptive")
        queue.put("only", "key")

        batch = await asyncio.wait_for(
            queue.collect(adaptive_eligible=False), timeout=0.03
        )

        self.assertEqual([item.payload for item in batch], ["only"])

    async def test_adaptive_minimum_batch_skips_unprofitable_b1_wait(self):
        queue = BatchQueue(
            4,
            0.2,
            8,
            policy="adaptive",
            adaptive_min_batch_size=2,
        )
        queue.put("only", "key")

        batch = await asyncio.wait_for(
            queue.collect(adaptive_eligible=True), timeout=0.03
        )

        self.assertEqual([item.payload for item in batch], ["only"])
        self.assertEqual(queue.adaptive_stats(), {})

    async def test_adaptive_backlog_waits_for_late_compatible_request(self):
        queue = BatchQueue(2, 0.2, 8, policy="adaptive")
        queue.put("first", "key")
        collection = asyncio.create_task(queue.collect(adaptive_eligible=True))
        await asyncio.sleep(0.01)
        queue.put("second", "key")

        batch = await asyncio.wait_for(collection, timeout=0.05)

        self.assertEqual([item.payload for item in batch], ["first", "second"])

    async def test_fixed_policy_waits_even_after_idle(self):
        queue = BatchQueue(2, 0.2, 8, policy="fixed")
        queue.put("first", "key")
        collection = asyncio.create_task(queue.collect(adaptive_eligible=False))
        await asyncio.sleep(0.01)
        queue.put("second", "key")

        batch = await asyncio.wait_for(collection, timeout=0.05)

        self.assertEqual([item.payload for item in batch], ["first", "second"])

    async def test_pipeline_waits_only_to_frozen_admitted_target(self):
        queue = BatchQueue(4, 0.05, 8, policy="pipeline")
        queue.put("first", "key")
        collection = asyncio.create_task(
            queue.collect(
                batch_size_limit=lambda key: 3,
                wait_for_target=True,
            )
        )
        await asyncio.sleep(0.002)
        queue.put("second", "key")
        queue.put("third", "key")

        batch = await asyncio.wait_for(collection, timeout=0.03)

        self.assertEqual(
            [item.payload for item in batch], ["first", "second", "third"]
        )

    async def test_pipeline_single_target_never_pays_wait_window(self):
        queue = BatchQueue(4, 0.2, 8, policy="pipeline")
        queue.put("only", "key")

        batch = await asyncio.wait_for(
            queue.collect(batch_size_limit=lambda key: 1, wait_for_target=True),
            timeout=0.03,
        )

        self.assertEqual([item.payload for item in batch], ["only"])

    async def test_queue_delay_deadline_prevents_additional_wait(self):
        queue = BatchQueue(
            2,
            0.2,
            8,
            policy="adaptive",
            max_queue_delay_seconds=0.005,
        )
        queue.put("old", "key")
        await asyncio.sleep(0.01)

        batch = await asyncio.wait_for(
            queue.collect(adaptive_eligible=True), timeout=0.03
        )

        self.assertEqual([item.payload for item in batch], ["old"])

    async def test_cancelled_request_releases_bounded_queue_slot(self):
        queue = BatchQueue(1, 0, 1, policy="opportunistic")
        first = queue.put("first", "key")
        with self.assertRaises(QueueFull):
            queue.put("full", "key")

        first.future.cancel()
        replacement = queue.put("replacement", "key")

        self.assertEqual(queue.qsize(), 1)
        self.assertEqual(replacement.queue_depth, 0)

    async def test_incompatible_arrival_does_not_extend_deadline(self):
        queue = BatchQueue(2, 0.02, 8, policy="adaptive")
        queue.put("a", "key-a")
        collection = asyncio.create_task(queue.collect(adaptive_eligible=True))
        await asyncio.sleep(0.005)
        queue.put("b", "key-b")

        first = await asyncio.wait_for(collection, timeout=0.05)
        second = await asyncio.wait_for(queue.collect(), timeout=0.03)

        self.assertEqual([item.payload for item in first], ["a"])
        self.assertEqual([item.payload for item in second], ["b"])

    async def test_adaptive_failures_enter_cooldown(self):
        queue = BatchQueue(
            2,
            0.005,
            8,
            policy="adaptive",
            adaptive_max_misses=2,
            adaptive_cooldown_seconds=0.2,
        )
        for index in range(2):
            queue.put(f"miss-{index}", "key")
            await queue.collect(adaptive_eligible=True)

        queue.put("cooled-down", "key")
        batch = await asyncio.wait_for(
            queue.collect(adaptive_eligible=True), timeout=0.02
        )
        stats = next(iter(queue.adaptive_stats().values()))

        self.assertEqual([item.payload for item in batch], ["cooled-down"])
        self.assertEqual(stats["attempts"], 2)
        self.assertEqual(stats["successes"], 0)
        self.assertEqual(stats["consecutive_misses"], 2)

    async def test_adaptive_success_resets_failed_probe_state(self):
        queue = BatchQueue(
            2,
            0.02,
            8,
            policy="adaptive",
            adaptive_max_misses=2,
        )
        queue.put("miss", "key")
        await queue.collect(adaptive_eligible=True)

        queue.put("first", "key")
        collection = asyncio.create_task(queue.collect(adaptive_eligible=True))
        await asyncio.sleep(0.002)
        queue.put("second", "key")
        batch = await collection
        stats = next(iter(queue.adaptive_stats().values()))

        self.assertEqual([item.payload for item in batch], ["first", "second"])
        self.assertEqual(stats["successes"], 1)
        self.assertEqual(stats["consecutive_misses"], 0)

    def test_rejects_unknown_policy(self):
        with self.assertRaises(ValueError):
            BatchQueue(4, 0.005, 32, policy="unknown")


if __name__ == "__main__":
    unittest.main()
