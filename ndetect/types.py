"""Type definitions for ndetect."""

from typing import NewType

# Type aliases for clarity
MinHashSignature = NewType('MinHashSignature', bytes)
SimilarityScore = NewType('SimilarityScore', float) 