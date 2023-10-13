import numpy as np

from napari_melt_pool_tracker import MeltPoolTrackerQWidget


# make_napari_viewer is a pytest fixture that returns a napari viewer object
# capsys is a pytest fixture that captures stdout and stderr output streams
def test_integration_of_steps(make_napari_viewer, capsys):
    # make viewer and add an image layer using our fixture
    viewer = make_napari_viewer()
    test_data = np.zeros((100, 100, 100))
    test_data[:, 50:, :] = 255
    viewer.add_image(test_data, name="test_image")

    # create our widget, passing in the viewer
    widget = MeltPoolTrackerQWidget(viewer)

    # test widget methods
    widget.speed_pos_groupbox.comboboxes["Input"].setCurrentText("test_image")
    widget._determine_laser_speed_and_position()
    widget.window_groupbox.comboboxes["Stack"].setCurrentText("test_image")
    widget.window_groupbox.comboboxes["Line"].setCurrentText("test_image_line")
    widget._reslice_with_moving_window()
    widget.filter_groupbox.comboboxes["Input"].setCurrentText(
        "test_image_resliced"
    )
    widget._filter()
    widget.radial_groupbox.comboboxes["Input"].setCurrentText(
        "test_image_resliced_filtered"
    )
    widget._calculate_radial_gradient()
    widget.annotate_surface_groupbox.comboboxes["Input"].setCurrentText(
        "test_image_resliced_filtered_radial_gradient"
    )
    widget.annotate_surface_groupbox.comboboxes["Surface"].setCurrentText(
        "test_image_resliced_filtered"
    )
    widget._annotate_surface_features()

    # read captured output and check that it's as we expected
    captured = capsys.readouterr()
    assert captured.out == ""


def test_comboboxes(make_napari_viewer, capsys):
    viewer = make_napari_viewer()
    test_data = np.zeros((100, 100, 100))
    test_data[:, 50:, :] = 255
    viewer.add_image(test_data, name="test_image_0")

    # create our widget, passing in the viewer
    widget = MeltPoolTrackerQWidget(viewer)

    for combobox, layer_type in widget.comboboxes:
        if layer_type == "image":
            assert combobox.count() == 1
        if layer_type == "shapes":
            assert combobox.count() == 0

    viewer.add_image(test_data, name="test_image_1")
    viewer.add_image(test_data, name="test_image_2")

    viewer.add_shapes(
        [[0, 10], [0, 10]], shape_type="line", name="test_line_0"
    )
    viewer.add_shapes(
        [[0, 10], [0, 10]], shape_type="line", name="test_line_1"
    )

    for combobox, layer_type in widget.comboboxes:
        if layer_type == "image":
            assert combobox.count() == 3
        if layer_type == "shapes":
            assert combobox.count() == 2

    del viewer.layers["test_image_1"]
    del viewer.layers["test_line_1"]

    for combobox, layer_type in widget.comboboxes:
        if layer_type == "image":
            assert combobox.count() == 2
        if layer_type == "shapes":
            assert combobox.count() == 1

    # read captured output and check that it's as we expected
    captured = capsys.readouterr()
    assert captured.out == ""


def test_determine_laser_speed_and_position(make_napari_viewer, capsys):
    viewer = make_napari_viewer()
    test_data = np.zeros((100, 100, 100))
    test_data[:, 50:, :] = 255
    name = "test_image"
    viewer.add_image(test_data, name=name)

    # create our widget, passing in the viewer
    widget = MeltPoolTrackerQWidget(viewer)

    expected_shape = (
        viewer.layers[name].data.shape[0],
        viewer.layers[name].data.shape[2],
    )

    for i in range(widget.speed_pos_groupbox.comboboxes["Mode"].count()):
        widget.speed_pos_groupbox.comboboxes["Input"].setCurrentText(name)
        mode = widget.speed_pos_groupbox.comboboxes["Mode"].itemText(i)
        widget.speed_pos_groupbox.comboboxes["Mode"].setCurrentIndex(i)
        widget._determine_laser_speed_and_position()
        assert np.all(
            viewer.layers[f"{name}_{mode}"].data.shape == expected_shape
        )
        assert len(viewer.layers[f"{name}_line"].shape_type) == 1
        assert viewer.layers[f"{name}_line"].shape_type[0] == "line"
        assert np.all(viewer.layers[f"{name}_line"].data[0].shape == (2, 2))
