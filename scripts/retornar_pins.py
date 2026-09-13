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

# Gera os PINs para as equipes de 1 a 10
for i in range(1, 11):
    print(f"Equipe {i}: PIN = {gerar_pin_equipe(i)}")