# napari-melt-pool-tracker

[![License BSD-3](https://img.shields.io/pypi/l/napari-melt-pool-tracker.svg?color=green)](https://github.com/faymanns/napari-melt-pool-tracker/raw/main/LICENSE)
[![PyPI](https://img.shields.io/pypi/v/napari-melt-pool-tracker.svg?color=green)](https://pypi.org/project/napari-melt-pool-tracker)
[![Python Version](https://img.shields.io/pypi/pyversions/napari-melt-pool-tracker.svg?color=green)](https://python.org)
[![tests](https://github.com/faymanns/napari-melt-pool-tracker/workflows/tests/badge.svg)](https://github.com/faymanns/napari-melt-pool-tracker/actions)
[![codecov](https://codecov.io/gh/faymanns/napari-melt-pool-tracker/branch/main/graph/badge.svg)](https://codecov.io/gh/faymanns/napari-melt-pool-tracker)
[![napari hub](https://img.shields.io/endpoint?url=https://api.napari-hub.org/shields/napari-melt-pool-tracker)](https://napari-hub.org/plugins/napari-melt-pool-tracker)

Plugin for tracking the width and depth of the melt pool and keyhole in x-ray images of laser powder bed fusion experiments.

----------------------------------

## Installation

You can install `napari-melt-pool-tracker` via [pip]:

    pip install napari-melt-pool-tracker

## Getting started with napari-melt-pool-tracker

### Reading
The plugin can read h5 files from the ID19 and TOMCAT beam lines.
When you open an h5 file napari will ask you to choose a reader for the file.
You have to select `Melt Pool Tracker` to read a files for one of the mentioned beamlines.
Once the data is loaded you can save the layer as a tif file if you would like.

### Pre-processing
For big images it is recommended to crop them in time and space to only include relevant parts of the stack.

### 1. Determine laser speed and position
This step helps you identify the laser in the images so that you can later reslice the stack with a moving window following the laser.
To do so it generates a projection of the stack along the y axis creating an x-t image. The position of the laser will appear as an oblique line in the projection.
1. Select the stack you would like to work on using the `Input` drop-down menu.
2. Select one of the three modes that determine how the projection along the y axis is done:
    Default: Maximum projection along y.
    Pre mean: First devide each frame of the stack by the mean projection along the t axis (this helps remove the background). Then perform a maximum projection along y.
    Post median: First perform a maximum projection along y, then devide the projected images by a median filtere version in x of itself. This help remove horizontal strips from the projection image.
3. Click `Run`! This should produce a new layer with the projected image and a shapes layer with a line.
4. Select the line layer and choose the `Select vertices` tool. Click on the line and drag the end points of the line until it matches the line of the laser seen in the projected image.

### 2. Reslice with moving window
This step reslices the stack with a moving window following the laser.
1. Select the input stack using the `Stack` drop-down menu.
2. Select the line layer containing the line that follows the laser position using the `Line` drop-down menu.
3. The `Left margin` and `Right margin` sliders determine the size of the window to the left and right of the laser position respecitvely.
4. Click `Run`! Depending on the size of your image this step might take a second. Once it is done the you should see three new layers: a resliced version of the stack, a shapes layer indicating the position of the laser based on the position of your annotation in the previous section, and a shapes layer with lines indicating the position of the window in the original image.
5. If the window is too small or too large for the melt pool, you can adjust its size using the margin sliders. If the autorun checkbox is ticked, the reslicing will run automatically when you move the sliders. For very large stacks you probably want to disable the autorun feature before you adjust the sliders.

### 3. Filter image
The next step aims to reduce noise in the images by applying a median filter. Select the resliced layer as your `Input`. The `Kerne` sliders determine the size of the median filter along the different axes. Just as for the reslicing the `auto run` option will rerun the filter when you change the values of the sliders. Median filtering is computationally costly, so you probably want to disable the `auto run` option of large stacks. After the median filter, this funtion also applies a otsu thresholding to remove the background. Don't forget to adjust the contrast at the end.

### 4. Calculate radial gradient
This step calculates the gray value gradient in the radial direction. The radial direction is with respect to a point on the surface. This points forms the origin. You can determine the horizontal position of the origin using the position slider. As input you should select the resliced and filtered version of the stack.
Don't forget to adjust the contrast for the new radial gradient layer.

### 5. Annotate
The annotation of points is done using the the [napari-cursor-tracker](https://www.napari-hub.org/plugins/napari-cursor-tracker) plugin.
Let say you want to annotate the depth of the melt pool. To do so first select any of the resliced layers as your reference image. The reference image is used to determine how many points you need to track. Then change the name in `Name of the tracked point` text box to e.g. 'MP depth'. Click `Add new layer`. A new points layer with the name you put in the text box should have been created and automatically selected as the active layer. The active layer determines which layer is updated when you are tracking. You can start the tracking by pressing 't' on your keyboard. If the `Auto play when tracking is started` box is ticked, the playback will start together with the tracking. You can adjust the playback parameters from the plugin or by right clicking on the play button. The frame rate might not reach the specified value, depending on the available resources on your machine. It is advided to set the `Loop mode` to 'once'. In the other modes you end up overwriting the points that you have already tracked. If you prefer to track the points very accuratly but more slowly, you can disactivate the `Auto play when tracking is started` option and scroll through the slices/frames one by one (hold down `ctrl`). Everytime the slice/frame index changes your mouse position is save. This allows you to carefully position you cursor before moving on to the next slice/frame.

### Saving and processing the results
You can save the 'window_coordinates' layer and the point layers with your tracked points as csv files and process them with the software of your choice.

## Contributing

Contributions are very welcome. Tests can be run with [tox], please ensure
the coverage at least stays the same before you submit a pull request.

## License

Distributed under the terms of the [BSD-3] license,
"napari-melt-pool-tracker" is free and open source software

## Issues

If you encounter any problems, please [file an issue] along with a detailed description.

[napari]: https://github.com/napari/napari
[Cookiecutter]: https://github.com/audreyr/cookiecutter
[@napari]: https://github.com/napari
[MIT]: http://opensource.org/licenses/MIT
[BSD-3]: http://opensource.org/licenses/BSD-3-Clause
[GNU GPL v3.0]: http://www.gnu.org/licenses/gpl-3.0.txt
[GNU LGPL v3.0]: http://www.gnu.org/licenses/lgpl-3.0.txt
[Apache Software License 2.0]: http://www.apache.org/licenses/LICENSE-2.0
[Mozilla Public License 2.0]: https://www.mozilla.org/media/MPL/2.0/index.txt
[cookiecutter-napari-plugin]: https://github.com/napari/cookiecutter-napari-plugin

[napari]: https://github.com/napari/napari
[tox]: https://tox.readthedocs.io/en/latest/
[pip]: https://pypi.org/project/pip/
[PyPI]: https://pypi.org/
