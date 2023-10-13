"""
This module is a reader plugin for h5 files from the TOMCAT and ID19 beamlines.

The TOMCAT beamline h5 containes the data in "exchange" --> "data". In the ID19
h5 file the data is stored in "image_stack".

If you need to extend the plugin to h5 files from other beamlines, please add
an additional `if` condition with the appropriate key to access the data.
"""

import h5py
import numpy as np


def napari_get_reader(path):
    """A basic implementation of a Reader contribution.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    function or None
        If the path is a recognized format, return a function that accepts the
        same path or list of paths, and returns a list of layer data tuples.
    """
    if isinstance(path, list):
        raise ValueError(
            "The napari-melt-pool-tracker plugin does not suport loading image stacks. Please load one h5 file at a time."
        )

    # if we know we cannot read the file, we immediately return None.
    if not path.endswith(".h5"):
        return None

    # otherwise we return the *function* that can read ``path``.
    return reader_function


def reader_function(path):
    """Take a path or list of paths and return a list of LayerData tuples.

    Readers are expected to return data as a list of tuples, where each tuple
    is (data, [add_kwargs, [layer_type]]), "add_kwargs" and "layer_type" are
    both optional.

    Parameters
    ----------
    path : str or list of str
        Path to file, or list of paths.

    Returns
    -------
    layer_data : list of tuples
        A list of LayerData tuples where each tuple in the list contains
        (data, metadata, layer_type), where data is a numpy array, metadata is
        a dict of keyword arguments for the corresponding viewer.add_* method
        in napari, and layer_type is a lower-case string naming the type of
        layer. Both "meta", and "layer_type" are optional. napari will
        default to layer_type=="image" if not provided
    """
    # handle both a string and a list of strings
    paths = [path] if isinstance(path, str) else path
    # load all files into array
    arrays = []
    for _path in paths:
        with h5py.File(_path, "r") as f:
            if "image_stack" in f:
                # ID19 data
                array = np.array(f["image_stack"])
            else:
                # Tomcat data
                array = np.array(f["exchange"]["data"])
            arrays.append(array)
    # stack arrays into single array
    data = np.squeeze(np.stack(arrays))

    # optional kwargs for the corresponding viewer.add_* method
    add_kwargs = {}

    layer_type = "image"  # optional, default is "image"
    return [(data, add_kwargs, layer_type)]
