import numpy as np

from napari_melt_pool_tracker import make_sample_data


def test_make_sample_data():
    returned_value = make_sample_data()
    assert isinstance(returned_value, list)
    for layer_data_tuple in returned_value:
        # Check that it is a layer data tuple
        assert isinstance(layer_data_tuple, tuple)
        assert len(layer_data_tuple) == 2
        assert isinstance(layer_data_tuple[0], np.ndarray)
        assert isinstance(layer_data_tuple[1], dict)

        # Check that the data is 3D
        data = layer_data_tuple[0]
        assert data.ndim == 3
