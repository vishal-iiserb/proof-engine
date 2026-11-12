"""
Quantitative position-sizing risk guards tested with Z3.
Checks whether scaled alpha signals can breach portfolio leverage limits.
"""

UNSAFE_POSITION_SIZER = """
def compute_position_size(capital, signal_bps, max_leverage):
    # Scale capital by basis-point alpha signal (10000 bps = 1x notional)
    exposure = (capital * signal_bps) // 10000
    if exposure < 0:
        abs_exposure = -exposure
    else:
        abs_exposure = exposure
    return abs_exposure
"""

SAFE_POSITION_SIZER = """
def compute_position_size(capital, signal_bps, max_leverage):
    exposure = (capital * signal_bps) // 10000
    if exposure < 0:
        abs_exposure = -exposure
    else:
        abs_exposure = exposure
    if abs_exposure > capital * max_leverage:
        raise ValueError("Position exposure exceeds maximum leverage cap")
    return abs_exposure
"""
