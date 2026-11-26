# Copyright (c) 2026 Almoon-D. All rights reserved.
"""The per-area PDF report and the professional export pack (MASTER_PLAN §4.6).

Both are made from a finished detailed map, on request, and are never sent anywhere: the
API hands them to the owner's browser as downloads. Rendering blocks, so it runs in a
worker thread.
"""

import asyncio
import tempfile
from pathlib import Path

from subphora.config import REPO_ROOT, Settings
from subphora.report.catalogue import Catalogue, CatalogueError
from subphora.report.document import render_pdf, report_html
from subphora.report.pack import build_pack
from subphora.services.export import ExportService, ReportData


class ReportService:
    def __init__(self, settings: Settings, export: ExportService) -> None:
        self._settings = settings.report
        self._export = export

    def _catalogue(self, data: ReportData) -> Catalogue:
        return Catalogue.load(
            self._settings.catalogue_path(REPO_ROOT), self._settings.zone(data.analysis.crs)
        )

    def _pdf(self, data: ReportData, catalogue: Catalogue) -> bytes:
        return render_pdf(report_html(data, catalogue, self._settings))

    async def pdf(self, area_id: str) -> bytes:
        """The area's report; raises ParcelError while its map is not done."""
        data = await self._export.data(area_id)
        catalogue = self._catalogue(data)
        return await asyncio.to_thread(self._pdf, data, catalogue)

    async def pack(self, area_id: str, media: bool, target: Path) -> None:
        """The area's export pack written to ``target`` (a ZIP)."""
        data = await self._export.data(area_id)
        catalogue = self._catalogue(data)
        with tempfile.TemporaryDirectory(prefix="subphora-pack-") as folder:
            layers = await self._export.write_layers(data, Path(folder), media)
            pdf = await asyncio.to_thread(self._pdf, data, catalogue)
            await asyncio.to_thread(build_pack, data, pdf, layers, catalogue, target)


__all__ = ["CatalogueError", "ReportService"]
