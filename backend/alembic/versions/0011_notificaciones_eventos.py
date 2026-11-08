"""Módulo 6: outbox de eventos, notificaciones internas y entregas de correo.

Revision ID: 0011_notificaciones_eventos
Revises: 0010_evaluacion_tras_cierre
Create Date: 2026-11-07

- `evento_outbox`: eventos registrados por los módulos 3 y 5 en su propia transacción.
- `notificacion`: avisos internos por destinatario (sin códigos ni notas en el mensaje).
- `entrega_correo`: estado del envío por correo de una notificación, con reintentos.

Todas las FK usan RESTRICT: no se borran usuarios, convocatorias ni participaciones, y el
historial de notificaciones tampoco se pierde en cascada. Las claves de idempotencia
(`notificacion.clave_idempotencia`, una entrega por notificación) evitan duplicados al
reprocesar un evento.

Autocontenida: no importa código de la aplicación.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0011_notificaciones_eventos"
down_revision: str | None = "0010_evaluacion_tras_cierre"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

estado_evento = postgresql.ENUM("PENDIENTE", "PROCESADO", "FALLIDO", name="estado_evento_outbox", create_type=False)
tipo_notificacion = postgresql.ENUM(
    "CONVOCATORIA", "CODIGO_REGENERADO", "REPROGRAMACION", "REVOCACION",
    "RESULTADOS_DISPONIBLES", "CALIFICACION_ACTUALIZADA", "RETROALIMENTACION",
    name="tipo_notificacion", create_type=False,
)
estado_entrega = postgresql.ENUM(
    "PENDIENTE", "EN_PROCESO", "ENVIADA", "FALLIDA", "CANCELADA", name="estado_entrega_correo", create_type=False
)

_UUID_PK = {"server_default": sa.text("gen_random_uuid()"), "nullable": False}
_AHORA = {"server_default": sa.text("now()"), "nullable": False}


def upgrade() -> None:
    for tipo in (estado_evento, tipo_notificacion, estado_entrega):
        tipo.create(op.get_bind(), checkfirst=True)

    op.create_table(
        "evento_outbox",
        sa.Column("id", sa.UUID(), **_UUID_PK),
        sa.Column("tipo", sa.String(length=60), nullable=False),
        sa.Column("sesion_id", sa.UUID(), nullable=False),
        sa.Column("datos", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'{}'::jsonb"), nullable=False),
        sa.Column("registrado_en", sa.DateTime(timezone=True), **_AHORA),
        sa.Column("estado", estado_evento, server_default=sa.text("'PENDIENTE'"), nullable=False),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("proximo_intento_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("procesado_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_error", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_evento_outbox")),
        sa.ForeignKeyConstraint(["sesion_id"], ["sesion.id"], name=op.f("fk_evento_outbox_sesion_id_sesion"), ondelete="RESTRICT"),
        sa.CheckConstraint("intentos >= 0", name=op.f("ck_evento_outbox_intentos_no_negativos")),
        sa.CheckConstraint(
            "(estado = 'PROCESADO') = (procesado_en IS NOT NULL)", name=op.f("ck_evento_outbox_procesado_segun_estado")
        ),
    )
    op.create_index("ix_evento_outbox_sesion_id", "evento_outbox", ["sesion_id"])
    op.create_index(
        "ix_evento_outbox_pendientes", "evento_outbox", ["registrado_en"], postgresql_where=sa.text("estado = 'PENDIENTE'")
    )

    op.create_table(
        "notificacion",
        sa.Column("id", sa.UUID(), **_UUID_PK),
        sa.Column("destinatario_id", sa.UUID(), nullable=False),
        sa.Column("tipo", tipo_notificacion, nullable=False),
        sa.Column("convocatoria_id", sa.UUID(), nullable=False),
        sa.Column("participacion_id", sa.UUID(), nullable=True),
        sa.Column("evento_id", sa.UUID(), nullable=True),
        sa.Column("clave_idempotencia", sa.String(length=120), nullable=False),
        sa.Column("titulo", sa.String(length=200), nullable=False),
        sa.Column("mensaje", sa.Text(), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), **_AHORA),
        sa.Column("leida", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("leida_en", sa.DateTime(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_notificacion")),
        sa.ForeignKeyConstraint(
            ["destinatario_id"], ["usuario.id"], name=op.f("fk_notificacion_destinatario_id_usuario"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["convocatoria_id"], ["convocatoria.id"], name=op.f("fk_notificacion_convocatoria_id_convocatoria"), ondelete="RESTRICT"
        ),
        sa.ForeignKeyConstraint(
            ["participacion_id"], ["participacion.id"], name=op.f("fk_notificacion_participacion_id_participacion"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["evento_id"], ["evento_outbox.id"], name=op.f("fk_notificacion_evento_id_evento_outbox"), ondelete="RESTRICT"
        ),
        sa.UniqueConstraint("clave_idempotencia", name=op.f("uq_notificacion_clave_idempotencia")),
        sa.CheckConstraint("(leida) = (leida_en IS NOT NULL)", name=op.f("ck_notificacion_lectura_coherente")),
        sa.CheckConstraint("length(btrim(titulo)) > 0", name=op.f("ck_notificacion_titulo_no_vacio")),
        sa.CheckConstraint(
            "tipo NOT IN ('CALIFICACION_ACTUALIZADA', 'RETROALIMENTACION') OR participacion_id IS NOT NULL",
            name=op.f("ck_notificacion_participacion_segun_tipo"),
        ),
    )
    op.create_index("ix_notificacion_convocatoria_id", "notificacion", ["convocatoria_id"])
    op.create_index("ix_notificacion_destinatario_creada", "notificacion", ["destinatario_id", "creada_en"])
    op.create_index("ix_notificacion_no_leidas", "notificacion", ["destinatario_id"], postgresql_where=sa.text("NOT leida"))

    op.create_table(
        "entrega_correo",
        sa.Column("id", sa.UUID(), **_UUID_PK),
        sa.Column("notificacion_id", sa.UUID(), nullable=False),
        sa.Column("estado", estado_entrega, server_default=sa.text("'PENDIENTE'"), nullable=False),
        sa.Column("huella_codigo", sa.String(length=64), nullable=True),
        sa.Column("intentos", sa.Integer(), server_default=sa.text("0"), nullable=False),
        sa.Column("creada_en", sa.DateTime(timezone=True), **_AHORA),
        sa.Column("ultimo_intento_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("proximo_intento_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("enviada_en", sa.DateTime(timezone=True), nullable=True),
        sa.Column("ultimo_error", sa.String(length=300), nullable=True),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_entrega_correo")),
        sa.ForeignKeyConstraint(
            ["notificacion_id"], ["notificacion.id"], name=op.f("fk_entrega_correo_notificacion_id_notificacion"),
            ondelete="RESTRICT",
        ),
        sa.UniqueConstraint("notificacion_id", name=op.f("uq_entrega_correo_notificacion_id")),
        sa.CheckConstraint("intentos >= 0", name=op.f("ck_entrega_correo_intentos_no_negativos")),
        sa.CheckConstraint("(estado = 'ENVIADA') = (enviada_en IS NOT NULL)", name=op.f("ck_entrega_correo_enviada_segun_estado")),
    )
    op.create_index(
        "ix_entrega_correo_pendientes",
        "entrega_correo",
        ["proximo_intento_en"],
        postgresql_where=sa.text("estado IN ('PENDIENTE', 'EN_PROCESO')"),
    )


def downgrade() -> None:
    op.drop_index("ix_entrega_correo_pendientes", table_name="entrega_correo")
    op.drop_table("entrega_correo")
    op.drop_index("ix_notificacion_no_leidas", table_name="notificacion")
    op.drop_index("ix_notificacion_destinatario_creada", table_name="notificacion")
    op.drop_index("ix_notificacion_convocatoria_id", table_name="notificacion")
    op.drop_table("notificacion")
    op.drop_index("ix_evento_outbox_pendientes", table_name="evento_outbox")
    op.drop_index("ix_evento_outbox_sesion_id", table_name="evento_outbox")
    op.drop_table("evento_outbox")
    for tipo in (estado_entrega, tipo_notificacion, estado_evento):
        tipo.drop(op.get_bind(), checkfirst=True)
