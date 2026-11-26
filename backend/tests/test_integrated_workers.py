"""Pruebas sin conexiones de base de datos; tambien ejecutables con unittest."""

import threading
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.main import _ciclo_de_vida, app
from app.workers.periodic import iniciar_en_segundo_plano


class PeriodicWorkerTests(unittest.TestCase):
    def test_retries_after_failure_and_stops(self):
        completed = threading.Event()
        calls = []

        def action():
            calls.append(1)
            if len(calls) == 1:
                raise RuntimeError("fallo temporal")
            completed.set()

        with self.assertLogs("app.workers.periodic", level="ERROR"):
            stop = iniciar_en_segundo_plano("test-retry", 0.01, action)
            try:
                self.assertTrue(completed.wait(2), "El worker no reintento")
            finally:
                stop.set()
        worker = next((t for t in threading.enumerate() if t.name == "test-retry"), None)
        if worker is not None:
            worker.join(1)
            self.assertFalse(worker.is_alive())
        self.assertGreaterEqual(len(calls), 2)

    def test_shutdown_interrupts_long_interval(self):
        ran = threading.Event()
        stop = iniciar_en_segundo_plano("test-stop", 3600, ran.set)
        self.assertTrue(ran.wait(2))
        worker = next(t for t in threading.enumerate() if t.name == "test-stop")
        stop.set()
        worker.join(1)
        self.assertFalse(worker.is_alive())


class WorkerLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_enabled_workers_start_and_stop_with_api(self):
        settings = SimpleNamespace(ENVIRONMENT="production", NOTIFICATIONS_WORKER_INTERVAL_SECONDS=0,
                                   PARTICIPATION_EXPIRATION_WORKER_INTERVAL_SECONDS=60,
                                   SESSION_EXPIRATION_WORKER_INTERVAL_SECONDS=300)
        stops = [threading.Event(), threading.Event()]
        with patch("app.main.get_settings", return_value=settings), patch(
            "app.workers.periodic.iniciar_en_segundo_plano", side_effect=stops
        ) as start:
            async with _ciclo_de_vida(app):
                self.assertEqual(start.call_count, 2)
                self.assertFalse(any(stop.is_set() for stop in stops))
            self.assertTrue(all(stop.is_set() for stop in stops))

    async def test_testing_never_starts_workers(self):
        settings = SimpleNamespace(ENVIRONMENT="testing", NOTIFICATIONS_WORKER_INTERVAL_SECONDS=30,
                                   PARTICIPATION_EXPIRATION_WORKER_INTERVAL_SECONDS=60,
                                   SESSION_EXPIRATION_WORKER_INTERVAL_SECONDS=300)
        with patch("app.main.get_settings", return_value=settings), patch(
            "app.workers.periodic.iniciar_en_segundo_plano"
        ) as periodic, patch("app.workers.notifications.runner.iniciar_en_segundo_plano") as notifications:
            async with _ciclo_de_vida(app):
                pass
            periodic.assert_not_called()
            notifications.assert_not_called()

    async def test_startup_failure_stops_previously_started_workers(self):
        settings = SimpleNamespace(ENVIRONMENT="production", NOTIFICATIONS_WORKER_INTERVAL_SECONDS=0,
                                   PARTICIPATION_EXPIRATION_WORKER_INTERVAL_SECONDS=60,
                                   SESSION_EXPIRATION_WORKER_INTERVAL_SECONDS=300)
        stop = threading.Event()
        with patch("app.main.get_settings", return_value=settings), patch(
            "app.workers.periodic.iniciar_en_segundo_plano", side_effect=[stop, RuntimeError("arranque fallido")]
        ):
            with self.assertRaises(RuntimeError):
                async with _ciclo_de_vida(app):
                    pass
        self.assertTrue(stop.is_set())
