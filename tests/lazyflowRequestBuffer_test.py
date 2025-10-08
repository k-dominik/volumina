###############################################################################
#   ilastik: interactive learning and segmentation toolkit
#
#       Copyright (C) 2011-2025, the ilastik developers
#                                <team@ilastik.org>
#
# This program is free software; you can redistribute it and/or
# modify it under the terms of the GNU General Public License
# as published by the Free Software Foundation; either version 2
# of the License, or (at your option) any later version.
#
# In addition, as a special exception, the copyright holders of
# ilastik give you permission to combine ilastik with applets,
# workflows and plugins which are not covered under the GNU
# General Public License.
#
# See the LICENSE file for details. License information is also available
# on the ilastik web site at:
#          http://ilastik.org/license.html
###############################################################################

from threading import Event
from typing import Optional
import pytest

from volumina.utility.lazyflowRequestBuffer import LazyflowRequestBuffer
from unittest.mock import MagicMock, Mock

from time import sleep


@pytest.mark.parametrize(
    "n_concurrent_tasks",
    [
        -1,
        -5,
        0,
    ],
)
def test_raises_on_init(n_concurrent_tasks: int):
    with pytest.raises(RuntimeError):
        _ = LazyflowRequestBuffer(n_concurrent_tasks)


class WaitingFunc:
    def __init__(self, side_effect: Optional[Exception] = None):
        self.side_effect = side_effect
        self.running: bool = False
        self.req_done: bool = False
        self.started: Event = Event()
        self.done: Event = Event()

    def __call__(self):
        self.running = True
        self.started.set()
        if self.side_effect is not None:
            raise self.side_effect
        while not self.req_done:
            sleep(0.1)
        self.running = False
        self.done.set()


def test_task_calls_decr():
    buffer = LazyflowRequestBuffer(1)
    viewPort = MagicMock()
    stack_id = object()

    waiting_func1 = WaitingFunc()

    buffer.submit(waiting_func1, priority=(-100,), viewport_ref=viewPort, stack_id=stack_id, tile_no=0)
    waiting_func1.started.wait(timeout=0.2)
    assert waiting_func1.running
    assert buffer._active == 1

    waiting_func1.req_done = True
    waiting_func1.done.wait(timeout=0.2)
    assert buffer._active == 0


def test_queuing():
    buffer = LazyflowRequestBuffer(1)
    viewPort = MagicMock()
    stack_id = object()

    waiting_func1 = WaitingFunc()
    waiting_func2 = WaitingFunc()

    buffer.submit(waiting_func1, priority=(-100,), viewport_ref=viewPort, stack_id=stack_id, tile_no=0)
    buffer.submit(waiting_func2, priority=(-120,), viewport_ref=viewPort, stack_id=stack_id, tile_no=0)
    waiting_func1.started.wait(timeout=0.2)
    waiting_func2.started.wait(timeout=0.2)
    assert waiting_func1.running
    # waiting_func2 is not running despite higher priority - submit is eagerly starting tasks as they come
    assert not waiting_func2.running

    waiting_func1.req_done = True
    waiting_func1.done.wait(timeout=0.2)
    waiting_func2.started.wait(timeout=0.2)
    assert waiting_func2.running

    waiting_func2.req_done = True
    waiting_func2.done.wait(timeout=0.2)
    assert not waiting_func2.running


def test_requests_are_cancelled():
    buffer = LazyflowRequestBuffer(1)
    viewPort = MagicMock()
    waiting_func = WaitingFunc()
    stack_id = object()
    buffer.submit(waiting_func, priority=(-100,), viewport_ref=viewPort, stack_id=stack_id, tile_no=0)
    waiting_func.started.wait()
    assert waiting_func.running
    buffer.clear_vp_res(viewPort, stack_id, keep_tiles=[])
    assert waiting_func.running
    for _ in range(10):
        buffer.submit(lambda: None, priority=(-1,), viewport_ref=viewPort, stack_id=stack_id, tile_no=1)
    buffer._cleared_tasks == 0
    buffer.clear_vp_res(viewPort, stack_id, keep_tiles=[])
    buffer._cleared_tasks == 10
    assert waiting_func.running
    waiting_func.req_done = True
    waiting_func.done.wait()
    assert not waiting_func.running

    assert viewPort.setTileDirty.call_count == 10


def test_raising_request():
    buffer = LazyflowRequestBuffer(1)
    viewPort = MagicMock()
    stack_id = object()

    m = WaitingFunc(side_effect=ValueError())
    m2 = Mock(side_effect=ValueError())
    m.req_done = True
    with pytest.raises(ValueError):
        buffer.submit(m2, priority=(-100,), viewport_ref=viewPort, stack_id=stack_id, tile_no=0)
        # assert m.running
