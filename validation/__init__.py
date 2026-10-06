"""Modulo de validacion de disenos con CODAME (CalcCodame.exe).

Uso:
    from validation.codame import validate_csv
    from validation import validate_csv   # tambien valido (import perezoso)
"""

__all__ = ["validate_csv", "validate_rows", "rows_from_dataframe"]


def __getattr__(name):
    if name in __all__:
        from . import codame
        return getattr(codame, name)
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
