"""Módulo 7: Seguimiento y Reportes (solo lectura).

Consulta el desarrollo y los resultados de las actividades académicas sin modificar ningún
dato: cada reporte se calcula en una transacción READ ONLY con aislamiento REPEATABLE READ
(ver `services/base.py`). No introduce patrones de diseño nuevos ni reimplementa la
calificación: la nota es siempre `participacion.nota_final` (módulo 5) y la corrección de
cada pregunta usa la misma regla (`opcion.es_correcta` de la opción elegida).
"""
