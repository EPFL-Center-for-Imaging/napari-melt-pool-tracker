import collections

import numpy as np
import pandas as pd
import scipy
import skimage
import sklearn.svm


def determine_laser_speed_and_position(
    stack,
    kernel_size_img=5,
    kernel_size_max=9,
):
    """
    Infers the laser position and speed by fitting a
    line in the spatio tempol resliced version of the
    image.

    Parameters
    ----------
    stack: np.ndarray
        The full size original images with one laser pass
        from right to left.
    kernel_size_img: int
        The length of the median filter applied along the
        direction of the laser.
    kernel_size_max: int
        The length of the median filter applied to the maxima.

    Returns
    -------
    coef : float
        The coefficient determining the slope of the line fitted.
    intecept : float
        The intercept of the line fitted.
    """
    resliced = np.swapaxes(stack, 0, 1)
    proj_resliced = np.max(resliced, axis=0)
    footprint = (
        np.eye(kernel_size_img, dtype=np.uint8)[:, ::-1]
        + np.eye(kernel_size_img, dtype=np.uint8, k=1)[:, ::-1]
        + np.eye(kernel_size_img, dtype=np.uint8, k=-1)[:, ::-1]
    )
    proj_resliced = skimage.filters.median(proj_resliced, footprint=footprint)
    proj_resliced = skimage.filters.sobel_h(proj_resliced)
    # proj_resliced = proj_resliced[10:]
    maxima = proj_resliced.argmax(0)  # + 10
    maxima = scipy.signal.medfilt(maxima, kernel_size=kernel_size_max)

    x = np.arange(len(maxima))
    svm = sklearn.svm.SVR(kernel="linear")
    svm.fit(x[:, np.newaxis], maxima)

    intercept = svm.intercept_[0]
    coef = svm.coef_[0][0]
    return proj_resliced, maxima, coef, intercept


def _reslice_with_moving_window(
    stack: np.array,
    coef: float,
    intercept: float,
    window_offset: int = 80,
    window_size: int = 400,
) -> (np.array, pd.DataFrame):
    """
    Spatio temporally reslices the data to fix
    the laser in a location. The sample appears to
    move. Uses a sliding window approach to make sure
    there is no distortion.

    Parameters
    ----------
    stack : np.ndarray
        Full size original data.
    coef : float
        Coefficient determining the laser speed.
        Can be obtained from 'determine_laser_speed_and_position'.
    intercept : float
        Position of the laser.
        Can be obtained from 'determine_laser_speed_and_position'.
    window_offset : int
        How far the window starts from the laser postion.
    window_size : int
        Size of the moving window.

    Returns
    -------
    resliced : np.ndarray
        A resliced version of the data keeping the laser in place.
    positions : pd.DataFrame
        A data frame containing the positions of the window and the laser
        with respect to the full size original data.
    """
    height = stack.shape[1]
    width = stack.shape[2]

    first_laser_pos = max(0, window_offset)
    last_laser_pos = min(
        round((-intercept) / coef), width - window_size + window_offset
    )
    if last_laser_pos - first_laser_pos < 1:
        raise ValueError("Window size and/or offset too large.")

    resliced = np.zeros(
        (last_laser_pos - first_laser_pos, height, window_size),
        dtype=stack.dtype,
    )

    positions = pd.DataFrame(
        columns=[
            "Time frame",
            "Laser position",
            "Window start",
            "Window stop",
        ],
        dtype=int,
    )

    for i, pos in enumerate(range(first_laser_pos, last_laser_pos)):
        t = round(intercept + pos * coef)
        resliced[i] = stack[
            t, :, pos - window_offset : pos - window_offset + window_size
        ]
        positions = pd.concat(
            (
                positions,
                pd.DataFrame(
                    {
                        "Time frame": (t,),
                        "Laser position": (pos,),
                        "Window start": (pos - window_offset,),
                        "Window stop": (pos - window_offset + window_size,),
                    }
                ),
            )
        )

    return resliced, positions


def determine_laser_speed_and_position_from_points(
    point1: (float, float), point2: (float, float)
) -> (float, float):
    """
    For some experiments the automatic detection of
    laser speed and positions does not work.
    In these cases the intercept can be determined
    from two manually specified points. The points
    can be chosen from the file saved by
    'determine_laser_speed_and_position'.

    Parameters
    ----------
    point1 : (float, float)
        Coordinates of point 1.
    point2 : (float, float)
        Coordinates of point 2.

    Returns
    -------
    coef : float
        Coefficient determining the slope of the line between the points.
    intercpet : float
        Intercept of the line between the points.
    """
    coef = (point2[1] - point1[1]) / (point2[0] - point1[0])
    intercept1 = point1[1] - coef * point1[0]
    intercept2 = point2[1] - coef * point2[0]
    return coef, np.mean((intercept1, intercept2))


def estimate_material_height(stack: np.array, x: int) -> int:
    return np.sum(np.isclose(stack[:, :, x], 1), axis=1)


def apply_2D_function_to_stack(
    stack: np.array, func: collections.abc.Callable
) -> np.array:
    """
    Helper function that allows runing 2D functions on each stack.
    """
    results = []
    for img in stack:
        results.append(func(img))
    stack = np.stack(tuple(results), axis=0)
    return stack


def radial_gradient(
    stack: np.array, center: (float, float), method: str = "sobel"
) -> (np.array, np.array):
    """
    Calculates the gradient in the raidal direction from a center.

    Parameters
    ----------
    stack : np.ndarray
        First dimension is time and the remaing two are space.
    method : str
        Filter to be used

    Returns
    -------
    rad_grad : np.ndarray
        Radial gradient images.
    angles : np.ndarray
        The direction of the gradient for each point.
    """
    if method == "sobel":
        x_grad = apply_2D_function_to_stack(stack, skimage.filters.sobel_v)
        y_grad = apply_2D_function_to_stack(stack, skimage.filters.sobel_h)
    elif method == "prewitt":
        x_grad = apply_2D_function_to_stack(stack, skimage.filters.prewitt_v)
        y_grad = apply_2D_function_to_stack(stack, skimage.filters.prewitt_h)
    elif method == "scharr":
        x_grad = apply_2D_function_to_stack(stack, skimage.filters.scharr_v)
        y_grad = apply_2D_function_to_stack(stack, skimage.filters.scharr_h)
    elif method == "farid":
        x_grad = apply_2D_function_to_stack(stack, skimage.filters.farid_v)
        y_grad = apply_2D_function_to_stack(stack, skimage.filters.farid_h)
    else:
        raise ValueError(
            f"`method` can only be 'sobel', 'prewitt', 'scharr', or 'farid', not {method}."
        )

    # Calculate radial vectors
    xx, yy = np.meshgrid(np.arange(stack.shape[2]), np.arange(stack.shape[1]))
    xx = np.tile(xx, (stack.shape[0], 1, 1))
    yy = np.tile(yy, (stack.shape[0], 1, 1))
    xx = xx - center[:, 1, np.newaxis, np.newaxis]
    yy = yy - center[:, 0, np.newaxis, np.newaxis]

    # Normalize directional vectors
    v_length = np.sqrt(xx**2 + yy**2)
    xx = xx / v_length
    yy = yy / v_length

    # Remove sign to avoid different signs infront and behind the laser
    xx = np.abs(xx)
    yy = np.abs(yy)

    # Project gradient in radial direction
    rad_grad = x_grad * xx + y_grad * yy

    return rad_grad, np.arctan2(x_grad, y_grad)


def calculate_radial_gradient(stack, xpos=115):
    material_height = estimate_material_height(stack, xpos)
    laser_positions = np.stack(
        (material_height, np.ones(stack.shape[0]) * xpos), axis=-1
    )
    radial_gradient_stack, gradient_directions = radial_gradient(
        stack, laser_positions, method="sobel"
    )
    return radial_gradient_stack


def incomplete_frames(stack: np.array) -> np.array:
    """
    Returns a mask of the frames that are not complete,
    i.e. the reslicing window extends beyond the bounds
    of the full size original data.
    """
    projection = np.sum(stack, axis=1)
    mask = np.isclose(projection, 0)
    mask = np.any(mask, axis=1)
    return mask


def get_surface(
    stack: np.array,
    surface_mask: np.array,
    top_offset: int = 0,
    bottom_offset: int = 20,
) -> np.array:
    """
    Extractes the pixels right below the surface of the sample.

    Parameters
    ----------
    stack : np.ndarray
        Data.
    surface_mask : np.ndarray
        A mask that is True outside of the sample.
    top_offset : int
        Number of pixels to exclude below the surface.
    bottom_offset : int
        Number of pixels to include below the surface.

    Returns
    -------
    surface : np.ndarray
        Array of height bottom_offset - top_offset.
        The other dimensions are identical to those
        of stack.
    """
    n_time_points = stack.shape[0]
    height = stack.shape[1]
    width = stack.shape[2]

    n_layers = bottom_offset - top_offset

    surface = np.zeros((n_time_points, n_layers, width), dtype=float)

    for i in range(n_time_points):
        for j in range(width):
            surface_height = np.max(np.where(surface_mask[i, :, j])[0])
            if height - surface_height - top_offset < 1:
                continue
            k = min((n_layers, height - surface_height - top_offset))
            surface[i, :k, j] = stack[
                i,
                surface_height + top_offset : surface_height + bottom_offset,
                j,
            ]
    return surface


def get_surface_image(stack, edges):
    mask = incomplete_frames(stack)
    stack = stack[~mask]
    edges = edges[~mask]
    surface_mask = np.isclose(stack, 1)
    surface = get_surface(
        edges[:-1], surface_mask[:-1], top_offset=0, bottom_offset=5
    )
    surface = np.sum(surface, axis=1)
    return surface
