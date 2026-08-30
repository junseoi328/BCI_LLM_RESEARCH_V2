from __future__ import annotations

# Snapshot of public API list pricing used only for approximate experiment-cost logging.
# Update this table when OpenAI pricing changes. Units: USD per 1M text tokens.
PRICING_USD_PER_MTOK = {
    "gpt-5.6-luna": (0.20, 1.20),
    "gpt-5.6-terra": (2.00, 12.00),
    "gpt-5.6-sol": (4.00, 20.00),
    "gpt-5.6": (4.00, 20.00),
}


def estimate_cost_usd(model: str, input_tokens: int, output_tokens: int) -> float | None:
    price = PRICING_USD_PER_MTOK.get(model)
    if not price:
        return None
    input_price, output_price = price
    return round((input_tokens / 1_000_000) * input_price + (output_tokens / 1_000_000) * output_price, 8)
