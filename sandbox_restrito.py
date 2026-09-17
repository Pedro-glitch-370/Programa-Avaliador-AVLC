import importlib
import numpy as np
import scipy
from RestrictedPython import compile_restricted, safe_globals
from RestrictedPython.Eval import default_guarded_getiter, default_guarded_getitem
from RestrictedPython.Guards import (
    full_write_guard,
    guarded_iter_unpack_sequence,
    guarded_unpack_sequence,
    safe_builtins,
)

MODULOS_PERMITIDOS = {"numpy", "scipy", "np"}

#classe para quando o código da equipe tentar algo fora da lista de permissões
class ViolacaoSandbox(Exception):
    pass

def _import_restrito(nome, globals=None, locals=None, fromlist=(), level=0):
    raiz = nome.split(".")[0]
    if raiz not in MODULOS_PERMITIDOS:
        raise ViolacaoSandbox(
            f"Import de '{nome}' não é permitido no ambiente de avaliação. "
            f"Módulos permitidos: {sorted(MODULOS_PERMITIDOS)}."
        )
    return importlib.import_module(nome)

#função para bloquear qualquer atributo "privado" ou dunder
_SEM_PADRAO = object()
def _getattr_restrito(objeto, nome, padrao=_SEM_PADRAO):
    if isinstance(nome, str) and nome.startswith("_"):
        raise ViolacaoSandbox(
            f"Acesso ao atributo '{nome}' não é permitido no ambiente de avaliação."
        )
    if padrao is not _SEM_PADRAO:
        return getattr(objeto, nome, padrao)
    return getattr(objeto, nome)

#função para reconhecer ndarray como tipo mutável seguro
def _write_restrito(objeto):
    if isinstance(objeto, np.ndarray):
        return objeto
    return full_write_guard(objeto)

#função com builtins plausíveis para o algoritmo
def _construir_globals_seguros():
    builtins_seguros = dict(safe_builtins)
    builtins_seguros.update({
        "__import__": _import_restrito,
        "len": len,
        "range": range,
        "enumerate": enumerate,
        "zip": zip,
        "map": map,
        "min": min,
        "max": max,
        "sum": sum,
        "abs": abs,
        "round": round,
        "sorted": sorted,
        "float": float,
        "int": int,
        "bool": bool,
        "list": list,
        "tuple": tuple,
        "dict": dict,
        "set": set,
        "print": lambda *a, **k: None,
    })

    ambiente = dict(safe_globals)
    ambiente["__builtins__"] = builtins_seguros
    ambiente["_getattr_"] = _getattr_restrito
    ambiente["_getitem_"] = default_guarded_getitem
    ambiente["_getiter_"] = default_guarded_getiter
    ambiente["_iter_unpack_sequence_"] = guarded_iter_unpack_sequence
    ambiente["_unpack_sequence_"] = guarded_unpack_sequence
    ambiente["_write_"] = _write_restrito
    ambiente["_print_"] = lambda *a, **k: None

    ambiente["np"] = np
    ambiente["numpy"] = np
    ambiente["scipy"] = scipy

    return ambiente

#compilar o código da equipe e retornar a função principal no namespace
def compilar_e_extrair_principal(codigo_fonte):
    resultado_compilacao = compile_restricted(
        codigo_fonte, filename="<codigo_equipe>", mode="exec"
    )

    ambiente = _construir_globals_seguros()
    namespace_local = {}

    exec(resultado_compilacao, ambiente, namespace_local)

    principal = namespace_local.get("principal") or ambiente.get("principal")
    if principal is None or not callable(principal):
        raise AttributeError(
            "O arquivo não contém a função 'principal(observada, mascara)'."
        )
    return principal