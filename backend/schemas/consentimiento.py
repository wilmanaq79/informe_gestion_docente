from pydantic import BaseModel


class PoliticaOut(BaseModel):
    version: str
    titulo: str
    texto: str
