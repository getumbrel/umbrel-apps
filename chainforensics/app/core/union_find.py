"""
Union-Find Data Structure for Advanced Cluster Detection

This module provides an efficient Union-Find (Disjoint Set Union) implementation
for detecting address clusters in Bitcoin transactions. It's used for advanced
cluster detection that goes beyond basic Common Input Ownership Heuristic (CIOH).

The Union-Find structure efficiently groups addresses that are linked through:
- Common input ownership (spending together)
- Change address heuristics
- Other clustering heuristics

Time Complexity:
- Union: O(α(n)) - nearly constant due to path compression
- Find: O(α(n)) - nearly constant
- α(n) is the inverse Ackermann function, grows extremely slowly

Security Note:
This is for blockchain forensics analysis only. It helps identify address
clusters but cannot prove ownership with 100% certainty.
"""

from typing import Dict, Set, List, Tuple
from dataclasses import dataclass


@dataclass
class ClusterEdge:
    """Represents an edge connecting two addresses in the cluster."""
    address1: str
    address2: str
    link_type: str  # "common_input", "change_heuristic", etc.
    txid: str
    confidence: float  # 0.0 to 1.0


class UnionFind:
    """
    Union-Find data structure with path compression and union by rank.

    This implementation is optimized for clustering Bitcoin addresses based on
    various heuristics. It maintains parent pointers and rank for efficient
    union and find operations.
    """

    def __init__(self):
        """Initialize empty Union-Find structure."""
        self.parent: Dict[str, str] = {}  # address -> parent address
        self.rank: Dict[str, int] = {}    # address -> rank (tree height)
        self.size: Dict[str, int] = {}    # address -> cluster size

    def add(self, address: str) -> None:
        """
        Add an address to the Union-Find structure.

        Args:
            address: Bitcoin address to add
        """
        if address not in self.parent:
            self.parent[address] = address
            self.rank[address] = 0
            self.size[address] = 1

    def find(self, address: str) -> str:
        """
        Find the root (representative) of the cluster containing this address.

        Uses path compression: all nodes along the path to root are updated
        to point directly to root, dramatically improving future lookups.

        Args:
            address: Bitcoin address to find root for

        Returns:
            Root address of the cluster
        """
        if address not in self.parent:
            self.add(address)

        # Path compression
        if self.parent[address] != address:
            self.parent[address] = self.find(self.parent[address])

        return self.parent[address]

    def union(self, address1: str, address2: str) -> bool:
        """
        Union two clusters containing address1 and address2.

        Uses union by rank: always attach smaller tree under root of larger tree
        to keep tree height small.

        Args:
            address1: First address
            address2: Second address

        Returns:
            True if addresses were in different clusters and were merged,
            False if they were already in the same cluster
        """
        root1 = self.find(address1)
        root2 = self.find(address2)

        if root1 == root2:
            return False  # Already in same cluster

        # Union by rank
        if self.rank[root1] < self.rank[root2]:
            self.parent[root1] = root2
            self.size[root2] += self.size[root1]
        elif self.rank[root1] > self.rank[root2]:
            self.parent[root2] = root1
            self.size[root1] += self.size[root2]
        else:
            self.parent[root2] = root1
            self.rank[root1] += 1
            self.size[root1] += self.size[root2]

        return True

    def get_cluster_size(self, address: str) -> int:
        """
        Get the size of the cluster containing this address.

        Args:
            address: Bitcoin address

        Returns:
            Number of addresses in the cluster
        """
        root = self.find(address)
        return self.size.get(root, 1)

    def get_clusters(self) -> Dict[str, Set[str]]:
        """
        Get all clusters as a dictionary mapping root -> set of addresses.

        Returns:
            Dictionary with cluster roots as keys and sets of addresses as values
        """
        clusters: Dict[str, Set[str]] = {}

        for address in self.parent:
            root = self.find(address)
            if root not in clusters:
                clusters[root] = set()
            clusters[root].add(address)

        return clusters

    def get_cluster_members(self, address: str) -> Set[str]:
        """
        Get all members of the cluster containing this address.

        Args:
            address: Bitcoin address

        Returns:
            Set of all addresses in the same cluster
        """
        root = self.find(address)
        clusters = self.get_clusters()
        return clusters.get(root, {address})
