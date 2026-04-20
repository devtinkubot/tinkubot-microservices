import re
from typing import Annotated

from pydantic import BeforeValidator


def _validar_jid(v: str) -> str:
    valor = (v or "").strip()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+", valor):
        raise ValueError("phone debe tener formato user@server")
    return valor


PhoneJID = Annotated[str, BeforeValidator(_validar_jid)]
