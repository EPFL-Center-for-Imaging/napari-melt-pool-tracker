"""
This module is an example of a barebones sample data provider for napari.

It implements the "sample data" specification.
see: https://napari.org/stable/plugins/guides.html?#sample-data

Replace code below according to your needs.
"""

from __future__ import annotations

import pathlib

import pkg_resources
import tifffile


def make_sample_data():
    """Generates an image"""
    # Return list of tuples
    # [(data1, add_image_kwargs1), (data2, add_image_kwargs2)]
    # Check the documentation for more information about the
    # add_image_kwargs
    # https://napari.org/stable/api/napari.Viewer.html#napari.Viewer.add_image
    DATA_DIR = pkg_resources.resource_filename(__name__, "data/")
    DATA_DIR = pathlib.Path(DATA_DIR)
    data = tifffile.imread(DATA_DIR / "wall1_H5.tif")
    return [(data, {"name": "wall1_H5"})]
