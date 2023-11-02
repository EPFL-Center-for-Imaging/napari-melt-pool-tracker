import collections

import numpy as np
import pandas as pd
import skimage


def determine_laser_speed_and_position(stack, mode):
    """
    Infers the laser position and speed by fitting a
    line in the spatio tempol resliced version of the
    image.

    Parameters
    ----------
    stack: np.ndarray
        The full size original images with one laser pass
        from right to left.
    mdoe: string
        The way the projection is computed.

    Returns
    -------
    proj_resliced : numpy array
        Resliced image with the height of the image cores
    coef : float
        The coefficient determining the slope of the line fitted.
    intecept : float
        The intercept of the line fitted.
    """
    modes = ["Pre mean", "Post median", "Default"]
    if mode not in modes:
        raise ValueError(f"Mode has to be in {modes}. You specified {mode}.")
    if mode == "Pre mean":
        stack = stack / np.mean(stack, axis=0)[np.newaxis, :, :]
    resliced = np.swapaxes(stack, 0, 2)
    proj_resliced = np.max(resliced, axis=1)
    if mode == "Post median":
        proj_resliced = (
            proj_resliced / np.median(proj_resliced, axis=1)[:, np.newaxis]
        )
    intercept = 0
    coef = proj_resliced.shape[0] / proj_resliced.shape[1]
    return (
        proj_resliced,
        coef,
        intercept,
    )


def reslice_with_moving_window(
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
    n_t = stack.shape[0]
    height = stack.shape[1]
    width = stack.shape[2]

    if coef == 0:
        raise ValueError("Coef is 0. This means the laser is not moving.")
    if (coef > 0 and intercept >= height) or (coef < 0 and intercept <= 0):
        raise ValueError(
            f"For this combination of coef and intercept the line does not intercept the image. (coef={coef}, intercept={intercept})"
        )

    resliced = np.zeros(
        (n_t, height, window_size),
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

    for t in range(n_t):
        laser_pos = coef * t + intercept
        laser_pos = round(laser_pos)
        if laser_pos > width:
            break
        start = laser_pos - window_offset
        stop = laser_pos - window_offset + window_size
        current_positions = pd.DataFrame(
            {
                "Time frame": (t,),
                "Laser position": (laser_pos,),
            }
        )
        if (start < 0 and stop < 0) or (start >= width and stop >= width):
            continue
        elif start < 0 and stop > width:
            raise ValueError("Window size too large for width of input stack.")
        elif start < 0:
            resliced[t, :, window_size - stop :] = stack[t, :, :stop]
            current_positions["Window start"] = 0
            current_positions["Window stop"] = stop
        elif stop > width:
            resliced[t, :, : width - start] = stack[t, :, start:]
            current_positions["Window start"] = start
            current_positions["Window stop"] = stack.shape[2] - 1
        else:
            resliced[t] = stack[t, :, start:stop]
            current_positions["Window start"] = start
            current_positions["Window stop"] = stop

        positions = pd.concat(
            (
                positions,
                current_positions,
            )
        )
    return resliced, positions


def determine_laser_speed_and_position_from_points(
    point1: (float, float), point2: (float, float)
) -> (float, float):
    """
    Calculates the coefficient and intercept of the line
    that passes throught the two specified points.

    Parameters
    ----------
    point1 : (float, float)
        Coordinates of point 1. The first coordinate is y (height)
        and the second component is x (widht).
    point2 : (float, float)
        Coordinates of point 2. The first coordinate is y (height)
        and the second component is x (widht).

    Returns
    -------
    coef : float
        Coefficient determining the slope of the line between the points.
    intercpet : float
        Intercept of the line between the points.
    """
    coef = (point2[0] - point1[0]) / (point2[1] - point1[1])
    intercept1 = point1[0] - coef * point1[1]
    intercept2 = point2[0] - coef * point2[1]
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
