"""Pydantic v2 models for the artifacts written to the exports/ directory.

These models are the boundary contract described in SRS section 10
(Modelo de Dados e Arquivos). They are pure data schemas: validation only,
no export logic. The Export Engine (not implemented in this scaffold) is
responsible for populating and serializing them.
"""
