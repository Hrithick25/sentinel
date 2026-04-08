"""
SENTINEL Consensus package

v4: Renamed BayesianConsensus → RiskAggregator.
    BayesianConsensus alias retained for backwards compatibility.
"""
from sentinel.consensus.risk_aggregator import RiskAggregator, BayesianConsensus

__all__ = ["RiskAggregator", "BayesianConsensus"]
