import hashlib
import hmac

CHAVE_MESTRE_TORNEIO = "torneio_algebra_linear_2026_secret"

def gerar_pin_equipe(equipe_id: int) -> str:
    mensagem = f"equipe_{equipe_id}".encode("utf-8")
    assinatura = hmac.new(
        CHAVE_MESTRE_TORNEIO.encode("utf-8"), 
        mensagem, 
        hashlib.sha256
    ).hexdigest()

    return assinatura[:6].upper()

def validar_pin_equipe(equipe_id: int, pin_informado: str) -> bool:
    pin_esperado = gerar_pin_equipe(equipe_id)
    return hmac.compare_digest(pin_esperado, pin_informado.strip().upper())