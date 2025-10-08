import logging

from typing import TYPE_CHECKING, Callable, Final
from queue import Empty, PriorityQueue
from threading import RLock

from volumina.pixelpipeline.slicesources import StackId
from lazyflow.request import Request


logger = logging.getLogger(__name__)


if TYPE_CHECKING:
    from volumina.tiling.tileprovider import TileProvider


class PrioTask:
    def __init__(
        self,
        func: "Request",
        task: Callable[[], None],
        prio: tuple[bool | int | float, ...],
        viewport_ref: "TileProvider",
        stack_id: StackId,
        tile_no: int,
    ):
        self._func: "Request" = func
        self._task = task
        self._tile_no = tile_no
        self._prio = prio
        self._vp = viewport_ref
        self._stack_id = stack_id

    @property
    def vp(self):
        return self._vp

    @property
    def stack_id(self):
        return self._stack_id

    @property
    def tile_no(self):
        return self._tile_no

    def run(self) -> None:
        self._func.submit()

    def __lt__(self, other: "PrioTask"):
        return self._prio < other._prio

    def cancel(self):
        self._func.cancel()


class LazyflowRequestBuffer:
    def __init__(self, n_concurrent_tasks: int = 8):
        assert n_concurrent_tasks > 0
        self._cleared_tasks: int = 0
        self._n_concurrent_tasks: Final[int] = n_concurrent_tasks
        self._queue: PriorityQueue[PrioTask] = PriorityQueue()
        self._active: int = 0
        self._lock = RLock()

    def submit(
        self,
        func: Callable[[], None],
        /,
        priority: tuple[bool | int | float, ...],
        viewport_ref: "TileProvider",
        stack_id: StackId,
        tile_no: int,
    ):
        root_priority = [1] + list(priority)
        req = Request(func, root_priority)
        self._queue.put(PrioTask(req, func, priority, viewport_ref, stack_id, tile_no))
        self.run()

    def run(self):
        with self._lock:
            while self._active < self._n_concurrent_tasks:
                try:
                    req = self._queue.get_nowait()
                except Empty:
                    return

                if req:
                    req._func._sig_execution_complete.subscribe(self.decr)
                    self._active += 1
                    req.run()

    def decr(self, *_args):
        with self._lock:
            self._active -= 1
        self.run()

    def clear(self):
        with self._lock:
            while True:
                try:
                    _ = self._queue.get_nowait()
                except Empty:
                    break

    def clear_vp_res(self, viewport: "TileProvider", stack_id: StackId, keep_tiles: list[int]):
        tmp_queue: list[PrioTask] = []
        with self._lock:
            while True:
                try:
                    task = self._queue.get_nowait()
                except Empty:
                    break

                if task.vp == viewport and task.stack_id != stack_id:
                    task.cancel()
                    self._cleared_tasks += 1
                    continue

                if task.vp == viewport and task.stack_id == stack_id and task.tile_no not in keep_tiles:
                    task.cancel()
                    self._cleared_tasks += 1
                    continue

                tmp_queue.append(task)

            for task in tmp_queue:
                self._queue.put(task)
        print(self._cleared_tasks)
