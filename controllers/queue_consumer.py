"""
Mixin that turns any manager into a queue consumer with a thread-pool.
Sub-classes must set:

    _queue : the shared Queue instance
    _tag   : a short emoji / prefix string for log lines

and implement:

    def _is_relevant(self, topic:str) -> bool
    def _process(self, device_id:int, topic:str, payload:str) -> None
"""

import threading
from queue import Empty
from concurrent.futures import ThreadPoolExecutor


class QueueConsumerMixin:
    _queue     = None     # override
    _tag       = "🪄"
    _n_threads = 4

    def _start_consumer(self):
        if not self._queue:
            raise RuntimeError(f"{self.__class__.__name__} forgot _queue")
        self._pool = ThreadPoolExecutor(max_workers=self._n_threads)
        threading.Thread(
            target=self._consumer_loop,
            name=f"{self.__class__.__name__}-Consumer",
            daemon=True,
        ).start()

    # ------------------------------------------------------------------

    def _consumer_loop(self):
        log = self.flask_app.logger
        while True:
            try:
                dev_id, topic, payload = self._queue.get(timeout=1)
            except Empty:
                continue

            if not self._is_relevant(topic):
                log.debug("%s ⤵︎ drop %s", self._tag, topic)
                self._queue.task_done()
                continue

            log.debug("%s ✔︎ take %s", self._tag, topic)
            self._pool.submit(self._safe_process, dev_id, topic, payload)
            self._queue.task_done()

    # wrapper so an exception in _process doesn’t kill the worker
    def _safe_process(self, device_id, topic, payload):
        try:
            self._process(device_id, topic, payload)
        except Exception as exc:
            self.flask_app.logger.exception(
                "%s ❌ exception while processing %s – %s", self._tag, topic, exc
            )
