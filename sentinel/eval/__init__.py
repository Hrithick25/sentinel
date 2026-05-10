"""
SENTINEL Eval Package
=======================
Adversarial mutation engine, normalizer, and benchmark utilities
for measuring recall on post-training mutated prompt injections.
"""
from sentinel.eval.mutation_engine import MutationLevel, generate_mutations
from sentinel.eval.normalizer import normalize_for_detection

__all__ = ["MutationLevel", "generate_mutations", "normalize_for_detection"]
