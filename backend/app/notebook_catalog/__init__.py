"""Catálogo oficial dos cadernos de classe — requisitos por seção."""

from app.notebook_catalog.sync import CATALOG_VERSION, sync_notebook_catalog

__all__ = ["CATALOG_VERSION", "sync_notebook_catalog"]
