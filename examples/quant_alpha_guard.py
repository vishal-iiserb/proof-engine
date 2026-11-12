"""
Quantitative position-sizing risk guards tested with Z3.
Checks whether net alpha-adjusted exposure can breach portfolio risk limits.
"""

UNSAFE_POSITION_SIZER = """
def compute_net_exposure(base_position, alpha_delta, max_exposure):
    exposure = base_position + alpha_delta
    if exposure < 0:
        abs_exposure = -exposure
    else:
        abs_exposure = exposure
    return abs_exposure
"""

SAFE_POSITION_SIZER = """
def compute_net_exposure(base_position, alpha_delta, max_exposure):
    exposure = base_position + alpha_delta
    if exposure < 0:
        abs_exposure = -exposure
    else:
        abs_exposure = exposure
    if abs_exposure > max_exposure:
        raise ValueError("Position exposure exceeds maximum risk limit")
    return abs_exposure
"""
