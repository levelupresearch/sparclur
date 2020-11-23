def _parse_poppler_size(size):
    """
    Parameters
    ----------
    size : Int or Tuple
        Pass a single int to render the document with the same number of pixels in the x and y directions. Otherwise,
        pass a tuple (width, height) for the width and height in pixels.
    Returns
    -------
    str
    """
    if not (isinstance(size, tuple) or isinstance(size, int) or isinstance(size, float)) or size is None:
        size_cmd = None
    else:
        if isinstance(size, int) or isinstance(size, float):
            size = tuple([size])
        if len(size) == 2:
            x_scale = -1 if size[0] is None else str(int(size[0]))
            y_scale = -1 if size[1] is None else str(int(size[1]))
            size_cmd = ['-scale-to-x', x_scale, '-scale-to-y', y_scale]
        elif len(size) == 1:
            scale = -1 if size[0] is None else str(int(size[0]))
            size_cmd = ['scale-to', scale]
    return size_cmd