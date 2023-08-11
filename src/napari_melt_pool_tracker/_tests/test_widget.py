import numpy as np

from napari_melt_pool_tracker import MeltPoolTrackerQWidget


# make_napari_viewer is a pytest fixture that returns a napari viewer object
# capsys is a pytest fixture that captures stdout and stderr output streams
def test_example_q_widget(make_napari_viewer, capsys):
    # make viewer and add an image layer using our fixture
    viewer = make_napari_viewer()
    viewer.add_image(np.random.random((100, 100, 100)))

    # create our widget, passing in the viewer
    widget = MeltPoolTrackerQWidget(viewer)

    # test widget methods
    widget._split()
    widget._determine_laser_speed_and_position()
    widget._reslice_with_moving_window()
    widget._filter()
    widget._calculate_radial_gradient()
    widget._annotate_surface_features()

    # read captured output and check that it's as we expected
    captured = capsys.readouterr()
    assert captured.out == ""
