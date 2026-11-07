"""Procesamiento de eventos y envío de notificaciones.

Una pasada (cron / Programador de tareas):

    python -m app.workers.notifications

Bucle propio cada N segundos:

    python -m app.workers.notifications --intervalo 30

Es seguro ejecutar varias instancias a la vez (FOR UPDATE SKIP LOCKED).
"""

import argparse
import logging

from app.workers.notifications.runner import ejecutar_periodicamente, ejecutar_una_vez


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Procesa el outbox de eventos y envía las notificaciones por correo.")
    parser.add_argument("--intervalo", type=int, default=0, help="Segundos entre pasadas; 0 = una sola pasada (por defecto).")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    if args.intervalo > 0:
        ejecutar_periodicamente(args.intervalo)
    else:
        ejecutar_una_vez()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
