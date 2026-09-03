"""Event-loop batch collection primitives for the semantic inference service.

The model worker is intentionally kept outside this module.  This keeps the queue
policy independent from PyTorch/Detectron2 and makes the latency-sensitive behavior
unit-testable on machines without a GPU.
"""

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Hashable, Optional


class QueueFull(Exception):
    """Raised when the bounded batch queue is saturated."""


@dataclass
class BatchItem:
    """One admitted request waiting for a compatible model batch."""

    payload: Any
    key: Hashable
    future: asyncio.Future
    enqueue_ns: int
    enqueue_time: float
    queue_depth: int
    dequeued_ns: Optional[int] = None


@dataclass
class _AdaptiveState:
    attempts: int = 0
    successes: int = 0
    consecutive_misses: int = 0
    cooldown_until: float = 0.0


class BatchQueue:
    """Collect compatible requests using opportunistic, fixed, or adaptive waits.

    ``adaptive`` only uses the millisecond-scale wait when requests were already
    queued as the previous model batch completed.  A request arriving to an idle
    GPU gets only a single event-loop turn for zero-cost coalescing, so the low-load
    path does not inherit a fixed timer penalty. ``pipeline`` only joins work that
    the service had already admitted at the preceding batch boundary.
    """

    POLICIES = frozenset(("opportunistic", "fixed", "adaptive", "pipeline"))

    def __init__(
        self,
        max_batch_size: int,
        max_wait_seconds: float,
        max_queue_size: int,
        policy: str = "opportunistic",
        max_queue_delay_seconds: float = 0.0,
        adaptive_min_batch_size: int = 1,
        adaptive_max_misses: int = 2,
        adaptive_cooldown_seconds: float = 1.0,
    ):
        self.max_batch_size = max(1, int(max_batch_size))
        self.max_wait_seconds = max(0.0, float(max_wait_seconds))
        self.max_queue_size = max(0, int(max_queue_size))
        self.max_queue_delay_seconds = max(
            0.0, float(max_queue_delay_seconds)
        )
        self.policy = str(policy).lower()
        if self.policy not in self.POLICIES:
            choices = ", ".join(sorted(self.POLICIES))
            raise ValueError(f"batch policy must be one of: {choices}")
        self.adaptive_min_batch_size = max(1, int(adaptive_min_batch_size))
        self.adaptive_max_misses = max(1, int(adaptive_max_misses))
        self.adaptive_cooldown_seconds = max(
            0.0, float(adaptive_cooldown_seconds)
        )

        self._items = deque()
        self._loop = None
        self._arrival = None
        self._adaptive_states = {}

    def _bind_loop(self):
        loop = asyncio.get_running_loop()
        if self._loop is None:
            self._loop = loop
            self._arrival = asyncio.Event()
        elif self._loop is not loop:
            if self._items:
                raise RuntimeError("cannot move a non-empty batch queue to another loop")
            self._loop = loop
            self._arrival = asyncio.Event()
        return loop

    def _prune_cancelled(self):
        if self._items:
            self._items = deque(
                item for item in self._items if not item.future.cancelled()
            )

    def qsize(self) -> int:
        self._prune_cancelled()
        return len(self._items)

    def adaptive_stats(self):
        """Return a JSON-friendly snapshot for diagnostics and tests."""
        return {
            repr(key): {
                "attempts": state.attempts,
                "successes": state.successes,
                "consecutive_misses": state.consecutive_misses,
                "cooldown_until": state.cooldown_until,
            }
            for key, state in self._adaptive_states.items()
        }

    def put(self, payload: Any, key: Hashable) -> BatchItem:
        """Append one admitted request without blocking the event loop."""
        loop = self._bind_loop()
        queue_depth = self.qsize()
        if self.max_queue_size and queue_depth >= self.max_queue_size:
            raise QueueFull(f"request queue is full ({self.max_queue_size})")

        item = BatchItem(
            payload=payload,
            key=key,
            future=loop.create_future(),
            enqueue_ns=time.perf_counter_ns(),
            enqueue_time=loop.time(),
            queue_depth=queue_depth,
        )
        self._items.append(item)
        self._arrival.set()
        return item

    @staticmethod
    def _mark_dequeued(item: BatchItem) -> BatchItem:
        if item.dequeued_ns is None:
            item.dequeued_ns = time.perf_counter_ns()
        return item

    def _take_first(self) -> Optional[BatchItem]:
        self._prune_cancelled()
        if not self._items:
            return None
        return self._mark_dequeued(self._items.popleft())

    def _take_matching(self, key: Hashable, limit: int):
        if limit <= 0:
            return []
        selected = []
        remaining = deque()
        while self._items:
            item = self._items.popleft()
            if item.future.cancelled():
                continue
            if item.key == key and len(selected) < limit:
                selected.append(self._mark_dequeued(item))
            else:
                remaining.append(item)
        self._items = remaining
        return selected

    async def _wait_for_first(self) -> BatchItem:
        while True:
            item = self._take_first()
            if item is not None:
                return item
            self._arrival.clear()
            await self._arrival.wait()

    async def _wait_for_arrival(self, deadline: float) -> bool:
        remaining = deadline - self._loop.time()
        if remaining <= 0:
            return False
        self._arrival.clear()
        try:
            await asyncio.wait_for(self._arrival.wait(), timeout=remaining)
        except asyncio.TimeoutError:
            return False
        return True

    async def collect(
        self,
        adaptive_eligible: bool = False,
        batch_size_limit: Optional[int] = None,
        wait_for_target: bool = False,
    ):
        """Return the next oldest-key batch.

        ``adaptive_eligible`` is set by the dispatcher after a model batch has run.
        It only has an effect when work is already waiting at method entry; if the
        GPU has to await the first item, adaptive collection dispatches immediately.
        """
        self._bind_loop()
        had_backlog = self.qsize() > 0
        first = self._take_first() if had_backlog else await self._wait_for_first()
        requested_limit = (
            batch_size_limit(first.key)
            if callable(batch_size_limit)
            else batch_size_limit
        )
        limit = self.max_batch_size
        if requested_limit is not None:
            limit = max(1, min(limit, int(requested_limit)))
        batch = [first]

        # Ready-aware policies get one event-loop turn to coalesce resize completions.
        # Opportunistic mode intentionally preserves the original immediate drain.
        if self.policy != "opportunistic":
            await asyncio.sleep(0)
        batch.extend(self._take_matching(first.key, limit - 1))
        if len(batch) >= limit:
            return batch

        pending_wait = self.policy == "pipeline" and wait_for_target
        speculative_wait = self.policy == "fixed" or (
            self.policy == "adaptive" and adaptive_eligible and had_backlog
        )
        if not pending_wait and not speculative_wait:
            return batch
        if self.max_wait_seconds <= 0:
            return batch
        if (
            speculative_wait
            and self.policy == "adaptive"
            and len(batch) < self.adaptive_min_batch_size
        ):
            return batch

        adaptive_key = (first.key, len(batch))
        adaptive_state = None
        if speculative_wait and self.policy == "adaptive":
            adaptive_state = self._adaptive_states.setdefault(
                adaptive_key, _AdaptiveState()
            )
            if self._loop.time() < adaptive_state.cooldown_until:
                return batch

        deadline = self._loop.time() + self.max_wait_seconds
        if self.max_queue_delay_seconds > 0:
            deadline = min(
                deadline,
                first.enqueue_time + self.max_queue_delay_seconds,
            )

        if deadline <= self._loop.time():
            return batch

        initial_size = len(batch)
        if adaptive_state is not None:
            adaptive_state.attempts += 1

        while len(batch) < limit:
            if not await self._wait_for_arrival(deadline):
                break
            batch.extend(
                self._take_matching(first.key, limit - len(batch))
            )

        if adaptive_state is not None:
            if len(batch) > initial_size:
                adaptive_state.successes += 1
                adaptive_state.consecutive_misses = 0
                adaptive_state.cooldown_until = 0.0
            else:
                adaptive_state.consecutive_misses += 1
                if adaptive_state.consecutive_misses >= self.adaptive_max_misses:
                    adaptive_state.cooldown_until = (
                        self._loop.time() + self.adaptive_cooldown_seconds
                    )
        return batch
