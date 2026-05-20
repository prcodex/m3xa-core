"""Pluggable backends — LLM, embeddings, vector DB, feed cache.

Vendor SDKs (anthropic, voyageai, lancedb) live only in this directory.
Everywhere else in the codebase uses the protocols defined here.
"""
