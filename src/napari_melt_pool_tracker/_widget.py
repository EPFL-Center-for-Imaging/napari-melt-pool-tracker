"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""


import numpy as np
from qtpy.QtWidgets import QPushButton, QVBoxLayout, QWidget

from napari_melt_pool_tracker import _utils


class MeltPoolTrackerQWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        btn1 = QPushButton("1. Split")
        btn1.clicked.connect(self._split)

        btn2 = QPushButton("2. Determine laser speed and position")
        btn2.clicked.connect(self._determine_laser_speed_and_position)

        btn3 = QPushButton("3. Reslice with moving window")
        btn3.clicked.connect(self._reslice_with_moving_window)

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(btn1)
        self.layout().addWidget(btn2)
        self.layout().addWidget(btn3)

        self.parameters = {}

    def _split(self):
        selected_layers = self.viewer.layers.selection
        t = self.viewer.dims.current_step[0]
        self.parameters["split_t"] = t
        layer = selected_layers.pop()
        data, meta, layer_type = layer.as_layer_data_tuple()
        if layer_type != "image":
            raise ValueError(
                "Can only split image layers. You have selected a layer of type {layer_type}."
            )
        data0 = data[:t]
        data1 = data[t:]
        name = meta["name"]
        meta["name"] = name + "_0"
        self.viewer.add_image(data0, **meta)
        meta["name"] = name + "_1"
        self.viewer.add_image(data1, **meta)

    def _determine_laser_speed_and_position(self):
        selected_layers = self.viewer.layers.selection
        if len(selected_layers) == 0:
            raise ValueError("No layers have been selected")
        if len(selected_layers) > 1:
            raise ValueError(
                "Can only detect laser position in one layer at a time. You have selected {len(selected_layers)} layers."
            )
        layer = selected_layers.pop()
        stack = layer.data

        (
            proj_resliced,
            maxima,
            coef,
            intercept,
        ) = _utils.determine_laser_speed_and_position(stack)

        y0 = 0
        x0 = (y0 - intercept) / coef
        if x0 < 0:
            x0 = 0
            y0 = intercept
        elif x0 > proj_resliced.shape[1]:
            x0 = proj_resliced.shape[1]
            y0 = coef * x0 + intercept

        y1 = proj_resliced.shape[0]
        x1 = (y1 - intercept) / coef
        if x1 < 0:
            x1 = 0
            y1 = intercept
        elif x1 > proj_resliced.shape[0]:
            x1 = proj_resliced.shape[0]
            y1 = coef * x1 + intercept

        self.points = np.stack([maxima, np.arange(len(maxima))], axis=-1)
        self.viewer.add_image(proj_resliced)
        self.viewer.add_points(data=self.points, face_color="cyan", size=8)
        self.viewer.add_shapes(
            data=[[y0, x0], [y1, x1]],
            shape_type="line",
            edge_color="red",
            edge_width=10,
            opacity=0.5,
        )

    def _reslice_with_moving_window(self):
        selected_layers = self.viewer.layers.selection
        if len(selected_layers) == 0:
            raise ValueError("No layers have been selected")
        if len(selected_layers) > 1:
            raise ValueError(
                "Can only detect laser position in one layer at a time. You have selected {len(selected_layers)} layers."
            )
        layer = selected_layers.pop()
        stack = layer.data

        shapes = self.viewer.layers["Shapes"].data
        if len(shapes) > 1:
            raise ValueError("Shapes layer should only containe one shape.")
        if len(shapes) == 0:
            raise ValueError("Shapes layers containes no shapes.")
        points = shapes[0]
        (
            coef,
            intercept,
        ) = _utils.determine_laser_speed_and_position_from_points(
            points[:, 0], points[:, 1]
        )

        resliced, self.position_df = _utils._reslice_with_moving_window(
            stack=stack, coef=coef, intercept=intercept
        )
        self.viewer.add_image(resliced)
