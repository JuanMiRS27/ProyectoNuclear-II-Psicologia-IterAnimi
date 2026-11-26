"""Bitácora de cambios de estado y fecha de actualización mantenidas por disparadores.

Revision ID: 0012_bitacora_fechas_trigger
Revises: 0011_notificaciones_eventos
Create Date: 2026-11-23

- `bitacora_estado`: registro de auditoría de solo inserción. Cada vez que se crea o cambia
  el estado de un caso, una sesión o una participación, un disparador AFTER guarda la tabla,
  el registro, el estado anterior, el nuevo, el usuario de la base de datos y la hora.
  No tiene FK a propósito: la bitácora conserva el historial aunque el registro se elimine.
- `trg_caso_estudio_actualizado_en`: la base fija `actualizado_en = now()` en cada UPDATE
  del caso, aunque el cambio no venga de la aplicación (p. ej., desde psql).
- `trg_bitacora_estado_solo_insercion`: impide modificar o borrar filas de la bitácora.

No requiere cambios en la aplicación: los disparadores actúan solos.
Autocontenida: no importa código de la aplicación.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0012_bitacora_fechas_trigger"
down_revision: str | None = "0011_notificaciones_eventos"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Tablas cuyo campo `estado` se audita.
_TABLAS_AUDITADAS = ("caso_estudio", "sesion", "participacion")

_FN_ACTUALIZADO_EN = """
CREATE FUNCTION fn_actualizar_fecha_modificacion() RETURNS trigger AS $$
BEGIN
    NEW.actualizado_en := now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;
"""

_FN_BITACORA = """
CREATE FUNCTION fn_registrar_cambio_estado() RETURNS trigger AS $$
BEGIN
    IF TG_OP = 'INSERT' THEN
        INSERT INTO bitacora_estado (tabla, registro_id, operacion, estado_anterior, estado_nuevo)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, NULL, NEW.estado::text);
    ELSIF NEW.estado IS DISTINCT FROM OLD.estado THEN
        INSERT INTO bitacora_estado (tabla, registro_id, operacion, estado_anterior, estado_nuevo)
        VALUES (TG_TABLE_NAME, NEW.id, TG_OP, OLD.estado::text, NEW.estado::text);
    END IF;
    RETURN NULL;  -- AFTER: el valor devuelto se ignora
END;
$$ LANGUAGE plpgsql;
"""

_FN_BITACORA_INMUTABLE = """
CREATE FUNCTION fn_bitacora_estado_inmutable() RETURNS trigger AS $$
BEGIN
    RAISE EXCEPTION 'La bitácora de estados no se modifica ni se borra.'
        USING ERRCODE = 'check_violation', CONSTRAINT = 'ck_bitacora_estado_solo_insercion';
END;
$$ LANGUAGE plpgsql;
"""


def upgrade() -> None:
    op.create_table(
        "bitacora_estado",
        sa.Column("id", sa.BigInteger(), sa.Identity(always=True), nullable=False),
        sa.Column("tabla", sa.String(length=63), nullable=False),
        sa.Column("registro_id", sa.UUID(), nullable=False),
        sa.Column("operacion", sa.String(length=10), nullable=False),
        sa.Column("estado_anterior", sa.String(length=30), nullable=True),
        sa.Column("estado_nuevo", sa.String(length=30), nullable=False),
        sa.Column("usuario_bd", sa.String(length=63), server_default=sa.text("current_user"), nullable=False),
        sa.Column("cambiado_en", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bitacora_estado")),
        sa.CheckConstraint("operacion IN ('INSERT', 'UPDATE')", name=op.f("ck_bitacora_estado_operacion")),
    )
    op.create_index("ix_bitacora_estado_registro", "bitacora_estado", ["tabla", "registro_id", "cambiado_en"])

    op.execute(_FN_ACTUALIZADO_EN)
    op.execute(
        "CREATE TRIGGER trg_caso_estudio_actualizado_en BEFORE UPDATE ON caso_estudio "
        "FOR EACH ROW EXECUTE FUNCTION fn_actualizar_fecha_modificacion();"
    )

    op.execute(_FN_BITACORA)
    for tabla in _TABLAS_AUDITADAS:
        op.execute(
            f"CREATE TRIGGER trg_{tabla}_bitacora_estado AFTER INSERT OR UPDATE OF estado ON {tabla} "
            "FOR EACH ROW EXECUTE FUNCTION fn_registrar_cambio_estado();"
        )

    op.execute(_FN_BITACORA_INMUTABLE)
    op.execute(
        "CREATE TRIGGER trg_bitacora_estado_solo_insercion BEFORE UPDATE OR DELETE ON bitacora_estado "
        "FOR EACH ROW EXECUTE FUNCTION fn_bitacora_estado_inmutable();"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_bitacora_estado_solo_insercion ON bitacora_estado;")
    op.execute("DROP FUNCTION IF EXISTS fn_bitacora_estado_inmutable();")
    for tabla in _TABLAS_AUDITADAS:
        op.execute(f"DROP TRIGGER IF EXISTS trg_{tabla}_bitacora_estado ON {tabla};")
    op.execute("DROP FUNCTION IF EXISTS fn_registrar_cambio_estado();")
    op.execute("DROP TRIGGER IF EXISTS trg_caso_estudio_actualizado_en ON caso_estudio;")
    op.execute("DROP FUNCTION IF EXISTS fn_actualizar_fecha_modificacion();")
    op.drop_index("ix_bitacora_estado_registro", table_name="bitacora_estado")
    op.drop_table("bitacora_estado")
