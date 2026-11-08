"""Exportación a CSV (formato mínimo de intercambio). Funciones puras, sin base de datos.

- UTF-8 con BOM (`utf-8-sig`): sigue siendo UTF-8 y permite que Excel muestre bien las tildes.
- Separador coma, todas las celdas entre comillas (`QUOTE_ALL`) y fin de línea CRLF (RFC 4180).
- Fechas en ISO 8601 y UTC (`2026-11-03T08:00:00Z`); decimales con punto y dos cifras ("2.20").
- Un valor nulo es una celda VACÍA: una nota sin registrar nunca se exporta como 0.
- Inyección de fórmulas (CSV injection): un texto que empieza por `=`, `+`, `-`, `@`, tabulador
  o retorno de carro (también en su forma de ancho completo, o tras cualquier secuencia de espacios,
  caracteres de control o caracteres invisibles de formato) se antepone con `'` para que la hoja de
  cálculo lo trate como texto. Los números no se alteran.
- Se genera en memoria y nunca se guarda en disco; el tamaño está acotado por
  `MAX_FILAS_EXPORTACION`.
"""

import csv
import enum
import io
import re
import unicodedata
import uuid
from collections.abc import Iterable, Sequence
from datetime import UTC, datetime
from decimal import Decimal

from app.core.exceptions import UnprocessableEntityError
from app.modules.evaluations.dominio import redondear

MAX_FILAS_EXPORTACION = 5000
TIPO_CONTENIDO_CSV = "text/csv; charset=utf-8"
_INICIOS_PELIGROSOS = ("=", "+", "-", "@", "\t", "\r", "\n", "＝", "＋", "－", "＠")
_NO_SEGURO_EN_NOMBRE = re.compile(r"[^a-z0-9_-]+")
_CATEGORIAS_INVISIBLES = frozenset({"Zs", "Zl", "Zp", "Cc", "Cf"})


class ExportacionExcedeLimiteError(UnprocessableEntityError):
    def __init__(self, limite: int = MAX_FILAS_EXPORTACION) -> None:
        super().__init__(
            f"El reporte supera el máximo de {limite} filas exportables; aplique filtros para reducirlo.",
            extra={"codigo": "EXPORTACION_EXCEDE_LIMITE", "limite": limite},
        )


def _sin_prefijo_invisible(valor: str) -> str:
    """Quita los caracteres iniciales que una hoja de cálculo puede ignorar antes de un indicador de fórmula.

    Espacios de cualquier tipo (Zs, Zl, Zp: espacio, NBSP, …), caracteres de control (Cc: NUL, tabulador
    vertical, avance de página, …) y de formato invisibles (Cf: espacio de ancho cero, BOM, marcas de dirección).
    """
    inicio = 0
    while inicio < len(valor) and unicodedata.category(valor[inicio]) in _CATEGORIAS_INVISIBLES:
        inicio += 1
    return valor[inicio:]


def texto_seguro(valor: str) -> str:
    """Neutraliza fórmulas: '=1+1' -> "'=1+1", también si van precedidas de espacios o caracteres invisibles."""
    if valor.startswith(_INICIOS_PELIGROSOS) or _sin_prefijo_invisible(valor).startswith(_INICIOS_PELIGROSOS):
        return "'" + valor
    return valor


def celda(valor: object) -> str:
    if valor is None:
        return ""
    if isinstance(valor, bool):
        return "Sí" if valor else "No"
    if isinstance(valor, enum.Enum):
        return texto_seguro(str(valor.value))
    if isinstance(valor, Decimal):
        return str(redondear(valor))
    if isinstance(valor, int):
        return str(valor)
    if isinstance(valor, datetime):
        if valor.tzinfo is None:
            raise ValueError("Las fechas exportadas deben tener zona horaria.")
        return valor.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(valor, uuid.UUID):
        return str(valor)
    return texto_seguro(str(valor))


def construir_csv(encabezados: Sequence[str], filas: Iterable[Sequence[object]], limite: int = MAX_FILAS_EXPORTACION) -> bytes:
    buffer = io.StringIO(newline="")
    escritor = csv.writer(buffer, quoting=csv.QUOTE_ALL, lineterminator="\r\n")
    escritor.writerow([texto_seguro(e) for e in encabezados])
    for n, fila in enumerate(filas, start=1):
        if n > limite:
            raise ExportacionExcedeLimiteError(limite)
        if len(fila) != len(encabezados):
            raise ValueError("Cada fila debe tener tantas celdas como encabezados.")
        escritor.writerow([celda(v) for v in fila])
    return buffer.getvalue().encode("utf-8-sig")


def nombre_archivo(ambito: str, identificador: uuid.UUID, tipo: str, ahora: datetime) -> str:
    """Nombre ASCII sin rutas ni caracteres especiales: reporte_sesion_<tipo>_<id>_<AAAAMMDD>.csv."""
    partes = [_NO_SEGURO_EN_NOMBRE.sub("", p.lower()) for p in ("reporte", ambito, tipo, identificador.hex[:8])]
    return "_".join(p for p in partes if p) + f"_{ahora.astimezone(UTC):%Y%m%d}.csv"


def cabeceras_descarga(nombre: str) -> dict[str, str]:
    return {
        "Content-Disposition": f'attachment; filename="{nombre}"',
        "Cache-Control": "no-store",
        "X-Content-Type-Options": "nosniff",
    }


__all__ = [
    "MAX_FILAS_EXPORTACION",
    "TIPO_CONTENIDO_CSV",
    "ExportacionExcedeLimiteError",
    "cabeceras_descarga",
    "celda",
    "construir_csv",
    "nombre_archivo",
    "texto_seguro",
]
