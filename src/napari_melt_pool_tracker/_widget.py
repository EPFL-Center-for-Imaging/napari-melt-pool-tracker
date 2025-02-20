"""
This module is an example of a barebones QWidget plugin for napari

It implements the Widget specification.
see: https://napari.org/stable/plugins/guides.html?#widgets

Replace code below according to your needs.
"""

import magicgui
import napari
import napari_cursor_tracker
import numpy as np
import scipy
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
        self,
        viewer,
        name,
        include_auto_run_and_overwrite=False,
        comboboxes=(("Input", napari.layers.Image),),
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
        self.viewer = viewer
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

        for name, item_type in comboboxes:
            if item_type in [napari.layers.Image, napari.layers.Shapes]:
                self.comboboxes[name] = magicgui.widgets.create_widget(
                    annotation=item_type
                )
                self.viewer.layers.events.inserted.connect(
                    self.comboboxes[name].reset_choices
                )
                self.viewer.layers.events.removed.connect(
                    self.comboboxes[name].reset_choices
                )
            else:
                self.comboboxes[name] = magicgui.widgets.create_widget(
                    widget_type=magicgui.widgets.ComboBox
                )

            self.layout.addWidget(QLabel(name), row, 1)
            self.layout.addWidget(self.comboboxes[name].native, row, 2)
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
        # Laser position
        #####################
        self.speed_pos_groupbox = StepWidget(
            viewer=self.viewer,
            name="1. Determine laser speed and position",
            comboboxes=[("Input", napari.layers.Image), ("Mode", str)],
        )
        self.speed_pos_groupbox.comboboxes["Mode"].set_choice("Default")
        self.speed_pos_groupbox.comboboxes["Mode"].set_choice("Pre mean")
        self.speed_pos_groupbox.comboboxes["Mode"].set_choice("Post median")
        self.speed_pos_groupbox.btn.clicked.connect(
            self._determine_laser_speed_and_position
        )

        #####################
        # Reslice
        #####################
        self.window_groupbox = StepWidget(
            viewer=self.viewer,
            name="2. Reslice with moving window",
            include_auto_run_and_overwrite=True,
            comboboxes=[
                ("Stack", napari.layers.Image),
                ("Line", napari.layers.Shapes),
            ],
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

        #####################
        # Denoise image
        #####################
        self.filter_groupbox = StepWidget(
            viewer=self.viewer,
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

        #####################
        # Radial gradient
        #####################
        self.radial_groupbox = StepWidget(
            viewer=self.viewer,
            name="4. Calculate radial gradient",
            sliders={"Position": (0, 100, 50)},
        )
        self.radial_groupbox.btn.clicked.connect(
            self._calculate_radial_gradient
        )

        #####################
        # Annotation
        #####################
        annotate_groupbox = QGroupBox("5. Annotate depths")
        annotate_layout = QVBoxLayout()
        annotate_groupbox.setLayout(annotate_layout)
        annotate_layout.addWidget(
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
        self.scroll_layout.addWidget(annotate_groupbox)

        self.scroll.setWidget(self.scroll_content)

        self.parameters = {}

    def _determine_laser_speed_and_position(self):
        input_layer = self.speed_pos_groupbox.comboboxes["Input"].value
        name = input_layer.name
        mode = self.speed_pos_groupbox.comboboxes["Mode"].native.currentText()
        layer_names = [
            f"{name}_{mode}",
            f"{name}_line",
        ]
        for layer_name in layer_names:
            if layer_name in self.viewer.layers:
                self.viewer.layers.remove(layer_name)

        stack = input_layer.data

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
        self._hide_old_layers(layer_names)

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
        stack_layer = self.window_groupbox.comboboxes["Stack"].value
        line_layer = self.window_groupbox.comboboxes["Line"].value
        name = stack_layer.name

        stack = self.viewer.layers[f"{name}"].data

        shapes = line_layer.data
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
        window_offset = left_margin
        window_size = left_margin + right_margin
        window_size = min(window_size, stack.shape[2] - window_offset)
        resliced, position_df = _utils.reslice_with_moving_window(
            stack=stack,
            coef=coef,
            intercept=intercept,
            window_offset=window_offset,
            window_size=window_size,
        )

        resliced_laser_coords = np.stack(
            [
                [0, resliced.shape[1] - 1],
                [window_offset, window_offset],
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
        input_layer = self.filter_groupbox.comboboxes["Input"].value
        name = input_layer.name
        stack = input_layer.data
        kernel_t = self.filter_groupbox.sliders["Kernel t"].value()
        kernel_y = self.filter_groupbox.sliders["Kernel y"].value()
        kernel_x = self.filter_groupbox.sliders["Kernel x"].value()
        name_filtered = f"{name}_filtered"
        filtered = scipy.ndimage.median_filter(
            stack, (kernel_t, kernel_y, kernel_x)
        )
        filtered_name = name_filtered
        if (
            self.filter_groupbox.overwrite_cb.isChecked()
            and filtered_name in self.viewer.layers
        ):
            self.viewer.layers.remove(filtered_name)
        self.viewer.add_image(filtered, name=filtered_name)
        self._hide_old_layers([name_filtered])

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
        input_layer = self.radial_groupbox.comboboxes["Input"].value
        name = input_layer.name
        stack = input_layer.data
        xpos = (
            self.radial_groupbox.sliders["Position"].value()
            / 100
            * stack.shape[2]
        )
        xpos = round(xpos)
        radial_gradient_stack = _utils.calculate_radial_gradient(
            stack, xpos=xpos
        )
        name_radial_gradient = f"{name}_radial_gradient"
        layer = self.viewer.add_image(
            radial_gradient_stack,
            name=name_radial_gradient,
        )
        self._hide_old_layers([layer.name])

    def _hide_old_layers(self, new_layer_names):
        for layer in self.viewer.layers:
            if layer.name not in new_layer_names:
                layer.visible = False
