# Copyright (c) 2026 Almoon-D. All rights reserved.
"""``/api/parcel``: an area's detailed potential map as a job, with the map layers the
front end draws once it is done: one image per layer over the area, with the legend of
the national layer of the same variable."""

from subphora.api.national import LegendClass, legend
from subphora.config import Settings
from subphora.domain import DomainModel
from subphora.domain.parcel_map import ParcelJob
from subphora.domain.potential import Variable

# The API's route of a layer's image.
PARCEL_IMAGE = "/api/parcel/{area_id}/layers/{layer_id}"


class ParcelLayer(DomainModel):
    id: str
    variable: Variable
    image: str
    opacity: float
    # Whether the layer is shown when the map is first drawn.
    visible: bool
    unit: str
    legend: tuple[LegendClass, ...]


class ParcelAnswer(DomainModel):
    job: ParcelJob
    # The layers to draw over the area; none until the job is done.
    layers: tuple[ParcelLayer, ...]


def parcel_answer(settings: Settings, job: ParcelJob) -> ParcelAnswer:
    if job.analysis is None:
        return ParcelAnswer(job=job, layers=())
    tiles = settings.national.tiles
    return ParcelAnswer(
        job=job,
        layers=tuple(
            ParcelLayer(
                id=layer.id,
                variable=layer.variable,
                image=PARCEL_IMAGE.format(area_id=job.id, layer_id=layer.id),
                opacity=layer.opacity,
                visible=layer.visible,
                unit=layer.unit,
                legend=legend(layer),
            )
            for layer in (tiles.layer(layer_id) for layer_id in settings.parcel.layers)
        ),
    )
