import numpy as np
import pytest

from napari_melt_pool_tracker import _utils


@pytest.fixture(params=[0, 1, 2])
def seed(request):
    return request.param


@pytest.fixture
def points(seed):
    rng = np.random.default_rng(seed=seed)
    points = rng.normal(size=(2, 2))
    return points


def test_determine_laser_speed_and_position_from_points(points):
    point0 = points[:, 0]
    point1 = points[:, 1]
    coef, intercept = _utils.determine_laser_speed_and_position_from_points(
        point0, point1
    )
    assert np.isclose(coef * point0[1] + intercept, point0[0])
    assert np.isclose(coef * point1[1] + intercept, point1[0])
