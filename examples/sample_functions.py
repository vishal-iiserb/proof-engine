"""Sample Python functions with boundary and arithmetic edge cases."""

BUGGY_PAYOUT = """
def process_transfer(balance, amount, fee):
    new_balance = balance - amount - fee
    return new_balance
"""

SAFE_PAYOUT = """
def process_transfer(balance, amount, fee):
    if balance < amount + fee:
        raise ValueError("Insufficient funds")
    new_balance = balance - amount - fee
    return new_balance
"""

OFF_BY_ONE_BUFFER = """
def validate_buffer_index(index, capacity):
    if index < 0 or index > capacity:
        raise IndexError("Index out of range")
    return index
"""

BUGGY_RATE_LIMITER = """
def consume_tokens(tokens_left, cost):
    remaining = tokens_left - cost
    return remaining
"""

BUGGY_DISCOUNT = """
def apply_coupon(price, discount):
    final_price = price - discount
    return final_price
"""
