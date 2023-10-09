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


@pytest.fixture(params=[-2, -0.5, 0, 0.1, 3])
def coef(request):
    return request.param


@pytest.fixture(params=[-50, 0, 20])
def intercept(request):
    return request.param


@pytest.fixture(params=[0, 10, 30])
def window_offset(request):
    return request.param


@pytest.fixture(params=[50, 100])
def window_size(request):
    return request.param


@pytest.fixture(params=[(2000, 200, 2016), (18000, 184, 1024)])
def stack_shape(request):
    return request.param


def test_reslice_with_moving_window(
    coef, intercept, window_offset, window_size, stack_shape
):
    stack = np.zeros(stack_shape)
    if (
        (coef == 0)
        or (coef > 0 and intercept >= stack_shape[1])
        or (coef < 0 and intercept <= 0)
    ):
        with pytest.raises(ValueError):
            result, positions = _utils.reslice_with_moving_window(
                stack, coef, intercept, window_offset, window_size
            )
    else:
        result, positions = _utils.reslice_with_moving_window(
            stack, coef, intercept, window_offset, window_size
        )
        assert result.shape[0] == stack.shape[0]
        assert result.shape[1] == stack.shape[1]
        assert result.shape[2] == window_size
