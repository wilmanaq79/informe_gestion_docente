from datetime import datetime

from pydantic import BaseModel


class NotificacionOut(BaseModel):
    id: int
    mensaje: str
    entrega_id: int | None
    leida: bool
    creado_en: datetime
