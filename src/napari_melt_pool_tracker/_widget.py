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
    QScrollArea,
    QSlider,
    QVBoxLayout,
    QWidget,
)

from napari_melt_pool_tracker import _utils


class StepWidget(QGroupBox):
    def __init__(
        self, name, include_auto_run_and_overwrite=False, sliders=None
    ):
        """
        Implements the widget unit used for a step in the pipeline.

        Sliders should be a dict where the key is the name of the slider and
        the value is tuple (min, max, initial_value) for the slider.
        """
        if sliders is None:
            sliders = {}

        super().__init__(name)
        self.layout = QGridLayout()
        self.setLayout(self.layout)
        self.sliders = {}
        row = 1
        if include_auto_run_and_overwrite:
            self.auto_run_cb = QCheckBox("auto run")
            self.auto_run_cb.setChecked(True)
            self.layout.addWidget(self.auto_run_cb, row, 1)
            self.overwrite_cb = QCheckBox("overwrite")
            self.overwrite_cb.setChecked(True)
            self.layout.addWidget(self.overwrite_cb, row, 2)
            row += 1
        for name, params in sliders.items():
            self.sliders[name] = QSlider(Qt.Horizontal)
            self.sliders[name].setMinimum(params[0])
            self.sliders[name].setMaximum(params[1])
            self.sliders[name].setValue(params[2])
            self.layout.addWidget(QLabel(name), row, 1)
            self.layout.addWidget(self.sliders[name], row, 2)
            row += 1
        self.btn = QPushButton("Run")
        self.layout.addWidget(self.btn, row, 1, 1, 2)


class MeltPoolTrackerQWidget(QWidget):
    def __init__(self, napari_viewer):
        super().__init__()
        self.viewer = napari_viewer

        #####################
        # Spliting
        #####################
        self.split_groupbox = StepWidget(name="1. Split")
        self.split_groupbox.btn.clicked.connect(self._split)

        #####################
        # Laser position
        #####################
        self.speed_pos_groupbox = StepWidget(
            name="2. Determine laser speed and position",
            include_auto_run_and_overwrite=True,
            sliders={
                "Median filter img": (1, 49, 5),
                "Median filter max": (1, 49, 9),
            },
        )
        self.speed_pos_groupbox.sliders[
            "Median filter img"
        ].valueChanged.connect(self._determine_laser_speed_and_position)
        self.speed_pos_groupbox.sliders[
            "Median filter max"
        ].valueChanged.connect(self._determine_laser_speed_and_position)
        self.speed_pos_groupbox.btn.clicked.connect(
            self._determine_laser_speed_and_position
        )

        #####################
        # Reslice
        #####################
        self.window_groupbox = StepWidget(
            name="3. Reslice with moving window",
            include_auto_run_and_overwrite=True,
            sliders={
                "Left margin": (10, 100, 30),
                "Right margin": (10, 200, 100),
            },
        )
        self.window_groupbox.sliders["Left margin"].valueChanged.connect(
            self._reslice_with_moving_window
        )
        self.window_groupbox.sliders["Right margin"].valueChanged.connect(
            self._reslice_with_moving_window
        )
        self.window_groupbox.btn.clicked.connect(
            self._reslice_with_moving_window
        )

        #####################
        # Denoise image
        #####################
        self.filter_groupbox = StepWidget(
            name="4. Filter image",
            include_auto_run_and_overwrite=True,
            sliders={
                "Kernel t": (1, 15, 7),
                "Kernel y": (1, 15, 3),
                "Kernel x": (1, 15, 3),
            },
        )
        self.filter_groupbox.sliders["Kernel t"].valueChanged.connect(
            self._filter
        )
        self.filter_groupbox.sliders["Kernel y"].valueChanged.connect(
            self._filter
        )
        self.filter_groupbox.sliders["Kernel x"].valueChanged.connect(
            self._filter
        )
        self.filter_groupbox.btn.clicked.connect(self._filter)

        #####################
        # Radial gradient
        #####################
        self.radial_groupbox = StepWidget(name="5. Calculate radial gradient")
        self.radial_groupbox.btn.clicked.connect(
            self._calculate_radial_gradient
        )

        #####################
        # Surface annotation
        #####################
        self.annotate_surface_groupbox = StepWidget(
            name="6. Annotate surface features"
        )
        self.annotate_surface_groupbox.btn.clicked.connect(
            self._annotate_surface_features
        )

        #####################
        # Depth annotation
        #####################
        annotate_depth_groupbox = QGroupBox("7. Annotate depths")
        annotate_depth_layout = QVBoxLayout()
        annotate_depth_groupbox.setLayout(annotate_depth_layout)
        annotate_depth_layout.addWidget(
            napari_cursor_tracker.CursorTracker(self.viewer)
        )

        # Set plugin layout
        self.layout = QVBoxLayout()
        self.setLayout(self.layout)

        # Make plugin scrollable
        self.scroll = QScrollArea(self)
        self.layout.addWidget(self.scroll)
        self.scroll.setWidgetResizable(True)
        self.scroll_content = QWidget(self.scroll)
        self.scroll_layout = QVBoxLayout(self.scroll_content)
        self.scroll_content.setLayout(self.scroll_layout)

        # Add individual widges to plugin
        self.scroll_layout.addWidget(self.split_groupbox)
        self.scroll_layout.addWidget(self.speed_pos_groupbox)
        self.scroll_layout.addWidget(self.window_groupbox)
        self.scroll_layout.addWidget(self.filter_groupbox)
        self.scroll_layout.addWidget(self.radial_groupbox)
        self.scroll_layout.addWidget(self.annotate_surface_groupbox)
        self.scroll_layout.addWidget(annotate_depth_groupbox)

        self.scroll.setWidget(self.scroll_content)

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

        if self.speed_pos_groupbox.overwrite_cb.isChecked():
            layer_names = [
                f"{self.parameters['name']}_proj",
                f"{self.parameters['name']}_points",
                f"{self.parameters['name']}_line",
            ]
            for layer_name in layer_names:
                if layer_name in self.viewer.layers:
                    self.viewer.layers.remove(layer_name)

        stack = self.viewer.layers[self.parameters["name"]].data

        kernel_size_img = self.speed_pos_groupbox.sliders[
            "Median filter img"
        ].value()
        kernel_size_max = self.speed_pos_groupbox.sliders[
            "Median filter max"
        ].value()
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
            points[0], points[1]
        )

        left_margin = self.window_groupbox.sliders["Left margin"].value()
        right_margin = self.window_groupbox.sliders["Right margin"].value()
        self.window_offset = left_margin
        self.window_size = left_margin + right_margin
        self.window_size = min(
            self.window_size, stack.shape[2] - self.window_offset
        )
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

        resliced_name = f"{self.parameters['name']}_resliced"
        pos_name = f"{self.parameters['name']}_laser_pos"
        if self.window_groupbox.overwrite_cb.isChecked():
            if resliced_name in self.viewer.layers:
                self.viewer.layers.remove(resliced_name)
            if pos_name in self.viewer.layers:
                self.viewer.layers.remove(pos_name)
        self.viewer.add_image(resliced, name=resliced_name)
        self.viewer.add_shapes(
            data=coords,
            shape_type="line",
            edge_color="blue",
            edge_width=1,
            opacity=0.5,
            name=pos_name,
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
        kernel_t = self.filter_groupbox.sliders["Kernel t"].value()
        kernel_y = self.filter_groupbox.sliders["Kernel y"].value()
        kernel_x = self.filter_groupbox.sliders["Kernel x"].value()
        filtered = skimage.filters.median(
            filtered, np.ones((kernel_t, kernel_y, kernel_x))
        )
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
