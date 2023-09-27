"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""

import napari_cursor_tracker
import numpy as np
import skimage
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QGridLayout,
    QGroupBox,
    QLabel,
    QPushButton,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from napari_melt_pool_tracker import _utils


class MeltPoolTrackerQWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        split_groupbox = QGroupBox("1. Split")
        split_layout = QVBoxLayout()
        split_groupbox.setLayout(split_layout)
        btn = QPushButton("Run")
        btn.clicked.connect(self._split)
        split_layout.addWidget(btn)

        speed_pos_groupbox = QGroupBox("2. Determine laser speed and position")
        speed_pos_layout = QGridLayout()
        speed_pos_groupbox.setLayout(speed_pos_layout)
        auto_run_cb = QCheckBox("auto run")
        self.overwrite_cb = QCheckBox("overwrite")
        self.slider_median_img = QSlider(Qt.Horizontal)
        self.slider_median_img.setMinimum(1)
        self.slider_median_img.setMaximum(49)
        self.slider_median_img.setValue(5)
        self.slider_median_img.valueChanged.connect(
            self._determine_laser_speed_and_position
        )
        self.slider_median_max = QSlider(Qt.Horizontal)
        self.slider_median_max.setMinimum(1)
        self.slider_median_max.setMaximum(49)
        self.slider_median_max.setValue(9)
        self.slider_median_max.valueChanged.connect(
            self._determine_laser_speed_and_position
        )
        btn = QPushButton("Run")
        btn.clicked.connect(self._determine_laser_speed_and_position)
        speed_pos_layout.addWidget(auto_run_cb, 1, 1)
        speed_pos_layout.addWidget(self.overwrite_cb, 1, 2)
        speed_pos_layout.addWidget(QLabel("Median filter img"), 2, 1)
        speed_pos_layout.addWidget(self.slider_median_img, 2, 2)
        speed_pos_layout.addWidget(QLabel("Median filter max"), 3, 1)
        speed_pos_layout.addWidget(self.slider_median_max, 3, 2)
        speed_pos_layout.addWidget(btn, 4, 1, 1, 2)

        window_groupbox = QGroupBox("3. Reslice with moving window")
        window_layout = QVBoxLayout()
        window_groupbox.setLayout(window_layout)
        btn = QPushButton("Run")
        btn.clicked.connect(self._reslice_with_moving_window)
        window_layout.addWidget(btn)

        filter_groupbox = QGroupBox("4. Filter image")
        filter_layout = QVBoxLayout()
        filter_groupbox.setLayout(filter_layout)
        btn = QPushButton("Run")
        btn.clicked.connect(self._filter)
        filter_layout.addWidget(btn)

        btn5 = QPushButton("5. Calculate radial gradient")
        btn5.clicked.connect(self._calculate_radial_gradient)
        radial_groupbox = QGroupBox("5. Calculate radial gradient")
        radial_layout = QVBoxLayout()
        radial_groupbox.setLayout(radial_layout)
        btn = QPushButton("Run")
        btn.clicked.connect(self._calculate_radial_gradient)
        radial_layout.addWidget(btn)

        annotate_surface_groupbox = QGroupBox("6. Annotate surface features")
        annotate_surface_layout = QVBoxLayout()
        annotate_surface_groupbox.setLayout(annotate_surface_layout)
        btn = QPushButton("Run")
        btn.clicked.connect(self._annotate_surface_features)
        annotate_surface_layout.addWidget(btn)

        annotate_depth_groupbox = QGroupBox("7. Annotate depths")
        annotate_depth_layout = QVBoxLayout()
        annotate_depth_groupbox.setLayout(annotate_depth_layout)
        annotate_depth_layout.addWidget(
            napari_cursor_tracker.CursorTracker(self.viewer)
        )

        self.setLayout(QVBoxLayout())
        self.layout().addWidget(split_groupbox)
        self.layout().addWidget(speed_pos_groupbox)
        self.layout().addWidget(window_groupbox)
        self.layout().addWidget(filter_groupbox)
        self.layout().addWidget(radial_groupbox)
        self.layout().addWidget(annotate_surface_groupbox)
        self.layout().addWidget(annotate_depth_groupbox)

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
        if "name" not in self.parameters:
            selected_layers = self.viewer.layers.selection
            if len(selected_layers) == 0:
                raise ValueError("No layers have been selected")
            if len(selected_layers) > 1:
                raise ValueError(
                    "Can only detect laser position in one layer at a time. You have selected {len(selected_layers)} layers."
                )
            layer = selected_layers.pop()
            self.parameters["name"] = layer.name

        if self.overwrite_cb.isChecked():
            layer_names = [
                f"{self.parameters['name']}_proj",
                f"{self.parameters['name']}_points",
                f"{self.parameters['name']}_line",
            ]
            for layer_name in layer_names:
                if layer_name in self.viewer.layers:
                    self.viewer.layers.remove(layer_name)

        stack = self.viewer.layers[self.parameters["name"]].data

        kernel_size_img = self.slider_median_img.value()
        kernel_size_max = self.slider_median_max.value()
        # Make kernel sizes odd
        if kernel_size_img % 2 == 0:
            kernel_size_img -= 1
        if kernel_size_max % 2 == 0:
            kernel_size_max -= 1

        (
            proj_resliced,
            maxima,
            coef,
            intercept,
        ) = _utils.determine_laser_speed_and_position(
            stack,
            kernel_size_img=kernel_size_img,
            kernel_size_max=kernel_size_max,
        )

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
        self.viewer.add_image(
            proj_resliced, name=f"{self.parameters['name']}_proj"
        )
        self.viewer.add_points(
            data=self.points,
            face_color="cyan",
            size=8,
            opacity=0.2,
            name=f"{self.parameters['name']}_points",
        )
        self.viewer.add_shapes(
            data=[[y0, x0], [y1, x1]],
            shape_type="line",
            edge_color="red",
            edge_width=10,
            opacity=0.5,
            name=f"{self.parameters['name']}_line",
        )
        self.viewer.layers[self.parameters["name"]].visible = False

    def _reslice_with_moving_window(self):
        stack = self.viewer.layers[f"{self.parameters['name']}"].data

        shapes = self.viewer.layers[f"{self.parameters['name']}_line"].data
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

        self.window_offset = 30
        self.window_size = min(130, stack.shape[2] - self.window_offset)
        resliced, self.position_df = _utils._reslice_with_moving_window(
            stack=stack,
            coef=coef,
            intercept=intercept,
            window_offset=self.window_offset,
            window_size=self.window_size,
        )

        n_frames = resliced.shape[0]
        ts = np.arange(n_frames)
        xs = np.ones(n_frames) * self.window_offset
        ys = np.zeros(n_frames)
        coord0 = np.stack([ts, ys, xs], axis=-1)
        ys = np.ones(n_frames) * (resliced.shape[1] - 1)
        coord1 = np.stack([ts, ys, xs], axis=-1)
        coords = np.stack([coord0, coord1], axis=1)

        self.viewer.add_image(
            resliced, name=f"{self.parameters['name']}_resliced"
        )
        self.viewer.add_shapes(
            data=coords,
            shape_type="line",
            edge_color="blue",
            edge_width=1,
            opacity=0.5,
            name=f"{self.parameters['name']}_laser_pos",
        )
        self.viewer.layers[f"{self.parameters['name']}"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_proj"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_points"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_line"].visible = False

    def _filter(self):
        stack = self.viewer.layers[f"{self.parameters['name']}_resliced"].data
        thresh = skimage.filters.threshold_otsu(stack)
        filtered = np.clip(stack, 0, thresh)
        filtered = filtered / np.max(filtered)
        filtered = skimage.filters.median(filtered, np.ones((7, 3, 3)))
        self.viewer.add_image(
            filtered, name=f"{self.parameters['name']}_resliced_filtered"
        )
        self.viewer.layers[f"{self.parameters['name']}"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_proj"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_points"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_line"].visible = False
        self.viewer.layers[
            f"{self.parameters['name']}_resliced"
        ].visible = False

    def _calculate_radial_gradient(self):
        stack = self.viewer.layers[
            f"{self.parameters['name']}_resliced_filtered"
        ].data
        radial_gradient_stack = _utils.calculate_radial_gradient(
            stack, xpos=self.window_offset
        )
        self.viewer.add_image(
            radial_gradient_stack,
            name=f"{self.parameters['name']}_radial_gradient",
        )
        self.viewer.layers[f"{self.parameters['name']}"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_proj"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_points"].visible = False
        self.viewer.layers[f"{self.parameters['name']}_line"].visible = False
        self.viewer.layers[
            f"{self.parameters['name']}_resliced"
        ].visible = False
        self.viewer.layers[
            f"{self.parameters['name']}_resliced_filtered"
        ].visible = False

    def _annotate_surface_features(self):
        stack = self.viewer.layers[
            f"{self.parameters['name']}_resliced_filtered"
        ].data
        edges = self.viewer.layers[
            f"{self.parameters['name']}_radial_gradient"
        ].data
        surface_image = _utils.get_surface_image(stack, edges)
        self.viewer.add_image(surface_image)
        self.viewer.add_shapes(name="Front Edge")
        self.viewer.add_shapes(name="Back Edge")
        self.viewer.add_shapes(name="DZ front Edge")
        self.viewer.add_shapes(name="DZ back Edge")
