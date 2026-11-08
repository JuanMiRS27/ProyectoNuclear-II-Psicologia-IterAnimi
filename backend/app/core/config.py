"""Configuración central de la aplicación, cargada desde variables de entorno o `.env`."""

import base64
import binascii
from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Simulador de Psicología Social - API"
    API_V1_PREFIX: str = "/api/v1"
    ENVIRONMENT: Literal["development", "testing", "production"] = "development"

    DATABASE_URL: str
    SQL_ECHO: bool = False

    # Sin valor por defecto: la aplicación no arranca si no se define una clave.
    JWT_SECRET_KEY: str = Field(min_length=32)
    # Solo algoritmos HMAC; nunca "none".
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, gt=0, le=60 * 24)

    # --- Módulo 3: sesiones y convocatorias ---
    # Plazo tras la hora de fin programada para que el cierre automático finalice una sesión.
    SESSION_AUTO_CLOSE_HOURS: int = Field(default=24, ge=0, le=24 * 30)
    # Limitación de intentos fallidos de acceso estudiantil (ventana deslizante).
    STUDENT_LOGIN_WINDOW_SECONDS: int = Field(default=900, gt=0)
    STUDENT_LOGIN_MAX_FAILURES_PER_EMAIL: int = Field(default=5, gt=0)
    STUDENT_LOGIN_MAX_FAILURES_PER_IP: int = Field(default=30, gt=0)
    # Permite al docente responsable consultar los códigos (hasta que el módulo 6 los envíe por correo).
    CONVOCATION_CODE_RETRIEVAL_ENABLED: bool = True
    # Expiración de SEGURIDAD del token estudiantil. Es independiente de `sesion.tiempo_max_min`:
    # el temporizador académico lo calculará el módulo 4 desde `participacion.inicio`.
    # Por defecto 300 min, por encima del máximo de participación (240 min).
    STUDENT_TOKEN_EXPIRE_MINUTES: int = Field(default=300, gt=0, le=60 * 24)

    # --- Módulo 5: evaluación y retroalimentación ---
    # Expiración del token de SOLO LECTURA para consultar resultados tras finalizar la sesión.
    STUDENT_RESULTS_TOKEN_EXPIRE_MINUTES: int = Field(default=60, gt=0, le=60 * 24)

    # --- Módulo 6: notificaciones y correo ---
    # Desactivado por defecto: desarrollo y pruebas funcionan sin servidor SMTP (las entregas
    # quedan PENDIENTES y nunca se envía un correo real). Al activarlo, el worker valida la
    # configuración completa (`adapters.crear_servicio_correo`) y falla de forma explícita.
    NOTIFICATIONS_EMAIL_ENABLED: bool = False
    SMTP_HOST: str | None = None
    SMTP_PORT: int = Field(default=587, gt=0, le=65535)
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: SecretStr | None = None
    SMTP_FROM_EMAIL: str | None = None
    SMTP_FROM_NAME: str = "Inter Nos"
    # STARTTLS (puerto 587) o TLS implícito (SMTP_USE_SSL, puerto 465). Sin cifrado solo se
    # admite hacia localhost (p. ej., Mailpit en desarrollo); nunca se desactiva la verificación.
    SMTP_USE_STARTTLS: bool = True
    SMTP_USE_SSL: bool = False
    SMTP_TIMEOUT_SECONDS: int = Field(default=10, gt=0, le=120)
    # URL pública de acceso al simulador. Sin valor por defecto: aún no existe un frontend
    # definitivo y no se inventa una dirección. Obligatoria para enviar convocatorias.
    SIMULATOR_ACCESS_URL: str | None = None
    # Desplazamiento horario fijo para presentar fechas en los mensajes (Colombia: UTC-05:00).
    NOTIFICATIONS_UTC_OFFSET_HOURS: int = Field(default=-5, ge=-12, le=14)
    NOTIFICATIONS_MAX_ATTEMPTS: int = Field(default=5, ge=1, le=20)
    NOTIFICATIONS_RETRY_BASE_SECONDS: int = Field(default=60, gt=0, le=3600)
    NOTIFICATIONS_RETRY_MAX_SECONDS: int = Field(default=3600, gt=0, le=86400)
    # Reserva de una entrega EN_PROCESO: si el worker cae, otra ejecución la retoma al vencer.
    NOTIFICATIONS_LEASE_SECONDS: int = Field(default=300, gt=0, le=3600)
    # Clave AES-256 (32 bytes en Base64 URL-safe) para cifrar los códigos de convocatoria en reposo.
    # Obligatoria y fuera de la base de datos y de Git. Generar con:
    #   python -c "import base64, os; print(base64.urlsafe_b64encode(os.urandom(32)).decode())"
    CONVOCATION_CODE_ENCRYPTION_KEY: str

    @field_validator("CONVOCATION_CODE_ENCRYPTION_KEY")
    @classmethod
    def _clave_aes_256(cls, valor: str) -> str:
        try:
            clave = base64.urlsafe_b64decode(valor.encode())
        except (binascii.Error, ValueError) as exc:
            raise ValueError("CONVOCATION_CODE_ENCRYPTION_KEY debe estar en Base64 URL-safe.") from exc
        if len(clave) != 32:
            raise ValueError("CONVOCATION_CODE_ENCRYPTION_KEY debe codificar exactamente 32 bytes (AES-256).")
        return valor

    @property
    def docs_enabled(self) -> bool:
        return self.ENVIRONMENT != "production"


@lru_cache
def get_settings() -> Settings:
    return Settings()
