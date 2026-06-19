from datetime import datetime, timedelta


def calcular_interes_compuesto(capital: float, tasa_anual: float, periodo_meses: int) -> dict:
    tasa_mensual = tasa_anual / 12 / 100
    monto_final = capital * (1 + tasa_mensual) ** periodo_meses
    interes_total = monto_final - capital
    return {
        "capital_inicial": round(capital, 2),
        "tasa_anual": tasa_anual,
        "periodo_meses": periodo_meses,
        "monto_final": round(monto_final, 2),
        "interes_total": round(interes_total, 2),
    }


def calcular_amortizacion(monto: float, tasa_anual: float, plazo_meses: int) -> dict:
    tasa_mensual = tasa_anual / 12 / 100
    cuota = monto * (tasa_mensual * (1 + tasa_mensual) ** plazo_meses) / ((1 + tasa_mensual) ** plazo_meses - 1)
    saldo = monto
    tabla = []
    for mes in range(1, plazo_meses + 1):
        interes = saldo * tasa_mensual
        abono = cuota - interes
        saldo -= abono
        tabla.append({
            "mes": mes,
            "cuota": round(cuota, 2),
            "interes": round(interes, 2),
            "abono": round(abono, 2),
            "saldo": round(abs(saldo), 2),
        })
    return {
        "monto": round(monto, 2),
        "tasa_anual": tasa_anual,
        "plazo_meses": plazo_meses,
        "cuota_mensual": round(cuota, 2),
        "total_intereses": round(sum(t["interes"] for t in tabla), 2),
        "total_pagado": round(cuota * plazo_meses, 2),
        "tabla": tabla[:12],
    }


def convertir_division(valor: float, tasa_cambio: float) -> dict:
    return {
        "valor_original": round(valor, 2),
        "tasa_cambio": tasa_cambio,
        "valor_convertido": round(valor * tasa_cambio, 2),
    }


def formatear_cop(valor: float) -> str:
    entero = int(round(valor))
    return f"$ {entero:,}".replace(",", ".")
