import numpy as np
import pandas as pd
import scipy
import skimage
import sklearn.svm


def determine_laser_speed_and_position(stack):
    """
    Infers the laser position and speed by fitting a
    line in the spatio tempol resliced version of the
    image.

    Parameters
    ----------
    stack: np.ndarray
        The full size original images with one laser pass
        from right to left.

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
        np.eye(5, dtype=np.uint8)[:, ::-1]
        + np.eye(5, dtype=np.uint8, k=1)[:, ::-1]
        + np.eye(5, dtype=np.uint8, k=-1)[:, ::-1]
    )
    proj_resliced = skimage.filters.median(proj_resliced, footprint=footprint)
    proj_resliced = skimage.filters.sobel_h(proj_resliced)
    proj_resliced = proj_resliced[10:]
    maxima = proj_resliced.argmax(0) + 10
    maxima = scipy.signal.medfilt(maxima, kernel_size=9)
    x = np.arange(len(maxima))
    # iso_forest = sklearn.ensemble.IsolationForest()
    # inliers = iso_forest.fit_predict(np.stack((x, maxima)).transpose())
    svm = sklearn.svm.SVR(kernel="linear")
    svm.fit(x[150:-150, np.newaxis], maxima[150:-150])

    # if name is not None:
    #     plt.imshow(proj_resliced)
    #     plt.scatter(x, maxima, c=inliers)
    #     x = np.linspace(0, len(maxima), 1000)
    #     plt.plot(x, svm.predict(x[:, np.newaxis]), color="red")
    #     plt.savefig(f"processed/spatio_temporal_reslicing/{name}.png")
    #     plt.close()

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

    first_pos = max(0, window_offset)
    last_laser_pos = min(
        round((-intercept) / coef), width - window_size + window_offset
    )

    resliced = np.zeros(
        (last_laser_pos - first_pos, height, window_size),
        dtype=stack.dtype,
    )

    positions = pd.DataFrame(
        columns=["Time frame", "Laser position", "Window start", "Window stop"]
    )

    for i, pos in enumerate(range(first_pos, last_laser_pos)):
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
