"""스코어링 팩터 레지스트리."""

from __future__ import annotations

from core.strategy.factors.macro_factor import MacroFactor
from core.strategy.factors.momentum_factor import MomentumFactor
from core.strategy.factors.mtf_factor import MTFFactor
from core.strategy.factors.structure_factor import StructureFactor
from core.strategy.factors.volatility_volume_factor import VolatilityVolumeFactor

DEFAULT_FACTORS = (
    MTFFactor(),
    MomentumFactor(),
    StructureFactor(),
    VolatilityVolumeFactor(),
    MacroFactor(),
)
