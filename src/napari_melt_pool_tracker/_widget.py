"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""

import napari_cursor_tracker
import numpy as np
import scipy
import skimage
from qtpy.QtCore import Qt
from qtpy.QtWidgets import (
    QCheckBox,
    QComboBox,
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
        self,
        name,
        include_auto_run_and_overwrite=False,
        comboboxes=("Input",),
        sliders=None,
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
        self.comboboxes = {}
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

        for name in comboboxes:
            self.comboboxes[name] = QComboBox()
            self.layout.addWidget(QLabel(name), row, 1)
            self.layout.addWidget(self.comboboxes[name], row, 2)
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
        self.comboboxes = []

        #####################
        # Laser position
        #####################
        self.speed_pos_groupbox = StepWidget(
            name="1. Determine laser speed and position",
            comboboxes=["Input", "Mode"],
        )
        self.speed_pos_groupbox.comboboxes["Mode"].addItem("Default")
        self.speed_pos_groupbox.comboboxes["Mode"].addItem("Pre mean")
        self.speed_pos_groupbox.comboboxes["Mode"].addItem("Post median")
        self.speed_pos_groupbox.btn.clicked.connect(
            self._determine_laser_speed_and_position
        )
        self._populate_combobox(
            self.speed_pos_groupbox.comboboxes["Input"], "image"
        )
        self.comboboxes.append(
            (self.speed_pos_groupbox.comboboxes["Input"], "image")
        )

        #####################
        # Reslice
        #####################
        self.window_groupbox = StepWidget(
            name="2. Reslice with moving window",
            include_auto_run_and_overwrite=True,
            comboboxes=["Stack", "Line"],
            sliders={
                "Left margin": (10, 350, 30),
                "Right margin": (10, 350, 100),
            },
        )
        self.window_groupbox.auto_run_cb.stateChanged.connect(
            self._reslice_auto_run
        )
        # Connect slider to match default of auto run checked
        self._reslice_auto_run()
        self.window_groupbox.btn.clicked.connect(
            self._reslice_with_moving_window
        )
        self._populate_combobox(
            self.window_groupbox.comboboxes["Stack"], "image"
        )
        self.comboboxes.append(
            (self.window_groupbox.comboboxes["Stack"], "image")
        )
        self._populate_combobox(
            self.window_groupbox.comboboxes["Line"], "shapes"
        )
        self.comboboxes.append(
            (self.window_groupbox.comboboxes["Line"], "shapes")
        )

        #####################
        # Denoise image
        #####################
        self.filter_groupbox = StepWidget(
            name="3. Filter image",
            include_auto_run_and_overwrite=True,
            sliders={
                "Kernel t": (1, 15, 7),
                "Kernel y": (1, 15, 3),
                "Kernel x": (1, 15, 3),
            },
        )
        self.filter_groupbox.auto_run_cb.stateChanged.connect(
            self._filter_auto_run
        )
        # Connect slider to match default of auto run checked
        self._filter_auto_run()
        self.filter_groupbox.btn.clicked.connect(self._filter)
        self._populate_combobox(
            self.filter_groupbox.comboboxes["Input"], "image"
        )
        self.comboboxes.append(
            (self.filter_groupbox.comboboxes["Input"], "image")
        )

        #####################
        # Radial gradient
        #####################
        self.radial_groupbox = StepWidget(
            name="4. Calculate radial gradient",
            sliders={"Position": (0, 100, 50)},
        )
        self.radial_groupbox.btn.clicked.connect(
            self._calculate_radial_gradient
        )
        self._populate_combobox(
            self.radial_groupbox.comboboxes["Input"], "image"
        )
        self.comboboxes.append(
            (self.radial_groupbox.comboboxes["Input"], "image")
        )

        #####################
        # Surface annotation
        #####################
        self.annotate_surface_groupbox = StepWidget(
            name="5. Annotate surface features",
            comboboxes=["Input", "Surface"],
        )
        self.annotate_surface_groupbox.btn.clicked.connect(
            self._annotate_surface_features
        )
        self._populate_combobox(
            self.annotate_surface_groupbox.comboboxes["Input"], "image"
        )
        self.comboboxes.append(
            (self.annotate_surface_groupbox.comboboxes["Input"], "image")
        )
        self._populate_combobox(
            self.annotate_surface_groupbox.comboboxes["Surface"], "image"
        )
        self.comboboxes.append(
            (self.annotate_surface_groupbox.comboboxes["Surface"], "image")
        )

        #####################
        # Depth annotation
        #####################
        annotate_depth_groupbox = QGroupBox("6. Annotate depths")
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
        self.scroll_layout.addWidget(self.speed_pos_groupbox)
        self.scroll_layout.addWidget(self.window_groupbox)
        self.scroll_layout.addWidget(self.filter_groupbox)
        self.scroll_layout.addWidget(self.radial_groupbox)
        self.scroll_layout.addWidget(self.annotate_surface_groupbox)
        self.scroll_layout.addWidget(annotate_depth_groupbox)

        self.scroll.setWidget(self.scroll_content)

        self.viewer.layers.events.inserted.connect(self._on_inserted_layer)
        self.viewer.layers.events.removed.connect(self._on_removed_layer)

        self.parameters = {}

    def _determine_laser_speed_and_position(self):
        name = self.speed_pos_groupbox.comboboxes["Input"].currentText()
        mode = self.speed_pos_groupbox.comboboxes["Mode"].currentText()
        layer_names = [
            f"{name}_{mode}",
            f"{name}_line",
        ]
        for layer_name in layer_names:
            if layer_name in self.viewer.layers:
                self.viewer.layers.remove(layer_name)

        stack = self.viewer.layers[name].data

        (
            proj_resliced,
            coef,
            intercept,
        ) = _utils.determine_laser_speed_and_position(stack, mode)

        x0, x1 = 0, proj_resliced.shape[1]
        y0 = coef * x0 + intercept
        y1 = coef * x1 + intercept

        self.viewer.add_image(proj_resliced, name=f"{name}_{mode}")
        self.viewer.add_shapes(
            data=[[y0, x0], [y1, x1]],
            shape_type="line",
            edge_color="red",
            edge_width=10,
            opacity=0.5,
            name=f"{name}_line",
        )
        self.viewer.layers[name].visible = False

    def _reslice_auto_run(self):
        if self.window_groupbox.auto_run_cb.isChecked():
            self.window_groupbox.sliders["Left margin"].valueChanged.connect(
                self._reslice_with_moving_window
            )
            self.window_groupbox.sliders["Right margin"].valueChanged.connect(
                self._reslice_with_moving_window
            )
        else:
            self.window_groupbox.sliders[
                "Left margin"
            ].valueChanged.disconnect()
            self.window_groupbox.sliders[
                "Right margin"
            ].valueChanged.disconnect()

    def _reslice_with_moving_window(self):
        name = self.window_groupbox.comboboxes["Stack"].currentText()
        line = self.window_groupbox.comboboxes["Line"].currentText()
        stack = self.viewer.layers[f"{name}"].data

        shapes = self.viewer.layers[line].data
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
        resliced, position_df = _utils.reslice_with_moving_window(
            stack=stack,
            coef=coef,
            intercept=intercept,
            window_offset=self.window_offset,
            window_size=self.window_size,
        )

        # n_frames = resliced.shape[0]
        # ts = np.arange(n_frames)
        # ys_top = np.zeros(n_frames)
        # ys_bottom = np.ones(n_frames) * (resliced.shape[1] - 1)

        # # Calculate coordinates for resliced laser position
        # xs = np.ones(n_frames) * self.window_offset
        # coord0 = np.stack([ts, ys_top, xs], axis=-1)
        # coord1 = np.stack([ts, ys_bottom, xs], axis=-1)
        # resliced_laser_coords = np.stack([coord0, coord1], axis=1)
        resliced_laser_coords = np.stack(
            [
                [0, resliced.shape[1] - 1],
                [self.window_offset, self.window_offset],
            ],
            axis=1,
        )

        window_lines = []
        for line_name in ["Window start", "Window stop", "Laser position"]:
            ts = position_df["Time frame"]
            xs = position_df[line_name]
            ys_top = np.zeros(len(ts))
            ys_bottom = np.ones(len(ts)) * (stack.shape[1] - 1)
            tops = np.stack([ts, ys_top, xs], axis=-1)
            bottoms = np.stack([ts, ys_bottom, xs], axis=-1)
            window_lines.append(np.stack([tops, bottoms], axis=1))
        window_lines = np.concatenate(window_lines, axis=0)

        window_name = f"{name}_window_coordinates"
        resliced_name = f"{name}_resliced"
        pos_name = f"{name}_laser_pos_resliced"
        if self.window_groupbox.overwrite_cb.isChecked():
            if window_name in self.viewer.layers:
                self.viewer.layers.remove(window_name)
            if resliced_name in self.viewer.layers:
                self.viewer.layers.remove(resliced_name)
            if pos_name in self.viewer.layers:
                self.viewer.layers.remove(pos_name)
        self.viewer.add_shapes(
            data=window_lines,
            shape_type="line",
            edge_color="blue",
            edge_width=1,
            opacity=0.5,
            name=window_name,
        )
        self.viewer.add_image(resliced, name=resliced_name)
        self.viewer.add_shapes(
            data=resliced_laser_coords,
            shape_type="line",
            edge_color="blue",
            edge_width=1,
            opacity=0.5,
            name=pos_name,
        )
        self._hide_old_layers([resliced_name, pos_name])

    def _filter(self):
        name = self.filter_groupbox.comboboxes["Input"].currentText()
        stack = self.viewer.layers[name].data
        thresh = skimage.filters.threshold_otsu(stack)
        filtered = np.clip(stack, 0, thresh)
        filtered = filtered / np.max(filtered)
        kernel_t = self.filter_groupbox.sliders["Kernel t"].value()
        kernel_y = self.filter_groupbox.sliders["Kernel y"].value()
        kernel_x = self.filter_groupbox.sliders["Kernel x"].value()
        filtered = scipy.ndimage.median_filter(
            filtered, (kernel_t, kernel_y, kernel_x)
        )
        filtered_name = f"{name}_filtered"
        if (
            self.filter_groupbox.overwrite_cb.isChecked()
            and filtered_name in self.viewer.layers
        ):
            self.viewer.layers.remove(filtered_name)
        self.viewer.add_image(filtered, name=filtered_name)
        self._hide_old_layers([f"{name}_filtered"])

    def _filter_auto_run(self):
        if self.filter_groupbox.auto_run_cb.isChecked():
            self.filter_groupbox.sliders["Kernel t"].valueChanged.connect(
                self._filter
            )
            self.filter_groupbox.sliders["Kernel y"].valueChanged.connect(
                self._filter
            )
            self.filter_groupbox.sliders["Kernel x"].valueChanged.connect(
                self._filter
            )
        else:
            self.filter_groupbox.sliders["Kernel t"].valueChanged.disconnect()
            self.filter_groupbox.sliders["Kernel y"].valueChanged.disconnect()
            self.filter_groupbox.sliders["Kernel x"].valueChanged.disconnect()

    def _calculate_radial_gradient(self):
        name = self.radial_groupbox.comboboxes["Input"].currentText()
        stack = self.viewer.layers[f"{name}"].data
        xpos = (
            self.radial_groupbox.sliders["Position"].value()
            / 100
            * stack.shape[2]
        )
        xpos = round(xpos)
        radial_gradient_stack = _utils.calculate_radial_gradient(
            stack, xpos=xpos
        )
        self.viewer.add_image(
            radial_gradient_stack,
            name=f"{name}_radial_gradient",
        )
        self._hide_old_layers([f"{name}_radial_gradient"])

    def _annotate_surface_features(self):
        surface_name = self.annotate_surface_groupbox.comboboxes[
            "Surface"
        ].currentText()
        stack_name = self.annotate_surface_groupbox.comboboxes[
            "Input"
        ].currentText()
        stack = self.viewer.layers[surface_name].data
        edges = self.viewer.layers[stack_name].data
        surface_image = _utils.get_surface_image(stack, edges)
        self.viewer.add_image(surface_image)
        self.viewer.add_shapes(name="MP front edge")
        self.viewer.add_shapes(name="MP back edge")
        self.viewer.add_shapes(name="DZ front edge")
        self.viewer.add_shapes(name="DZ back edge")
        self._hide_old_layers(
            [
                "surface_image",
                "MP front edge",
                "MP back edge",
                "DZ front edge",
                "DZ back edge",
            ]
        )

    def _on_inserted_layer(self, event):
        layer = event.value
        for combobox, layer_type in self.comboboxes:
            if self._val_layer_type(layer, layer_type):
                combobox.addItem(layer.name)

    def _on_removed_layer(self, event):
        layer = event.value
        for combobox, _ in self.comboboxes:
            for index in range(combobox.count()):
                if layer.name == combobox.itemText(index):
                    combobox.removeItem(index)

    def _val_layer_type(self, layer, layer_type):
        return layer.as_layer_data_tuple()[2] == layer_type

    def _populate_combobox(self, combobox, layer_type):
        for layer in self.viewer.layers:
            if self._val_layer_type(layer, layer_type):
                combobox.addItem(layer.name)

    def _hide_old_layers(self, new_layer_names):
        for layer in self.viewer.layers:
            if layer.name not in new_layer_names:
                layer.visible = False
