import re


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


def _pdftoppm_clean_message(err):
    cleaned = re.sub(r"Couldn't", 'Could not', err)
    cleaned = re.sub(r"wasn't", 'was not', cleaned)
    cleaned = re.sub(r"isn't", 'is not', cleaned)
    cleaned = re.sub(r' \([a-f\d]+\)', '', cleaned)
    cleaned = re.sub(r'\s{0, 1}\<[^>]+\>\s{0, 1}', ' ', cleaned)
    cleaned = re.sub(r"\'[^']+\'", "\'<x>\'", cleaned)
    cleaned = re.sub(r'xref num \d+', 'xref num <x>', cleaned)
    cleaned = re.sub(r'\(page \d+\)', '', cleaned)
    cleaned = re.sub(r'\(bad size: \d+\)', '(bad size)', cleaned)
    cleaned = 'Syntax Error: Unknown operator' if cleaned.startswith('Syntax Error: Unknown operator') else cleaned
    cleaned = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
        'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
    cleaned = 'Syntax Error: Invalid XRef entry' if cleaned.startswith(
        'Syntax Error: Invalid XRef entry') else cleaned
    cleaned = re.sub(r'Corrupt JPEG data: \d+ extraneous bytes before marker [xa-f\d]{4, 4}',
                     'Corrupt JPEG data: extraneous bytes before marker', cleaned)
    cleaned = re.sub(r'Corrupt JPEG data: found marker [xa-f\d]{4, 4} instead of RST\d+',
                     'Corrupt JPEG data: found marker <x> instead of RSTx', cleaned)
    cleaned = re.sub(r'Syntax Error: \d+ extraneous byte[s]{0, 1} after segment',
                     'Syntax Error: extraneous bytes after segment', cleaned)
    cleaned = re.sub(r'Syntax Error: AnnotWidget::layoutText, cannot convert U\+[A-F\d]+',
                     'Syntax Error: AnnotWidget::layoutText, cannot convert U+xxxx', cleaned)
    cleaned = re.sub(r'Arg #\d+', 'Arg ', cleaned)
    cleaned = re.sub(r'Failed to parse XRef entry \[\d+\].', 'Failed to parse XRef entry.', cleaned)
    cleaned = re.sub(
        r'Syntax Error: Softmask with matte entry \d+ x \d+ must have same geometry as the image \d+ x \d+',
        'Syntax Error: Softmask with matte entry must have same geometry as the image', cleaned)
    cleaned = re.sub(r'Syntax Error: Unknown marker segment \d+ in JPX tile-part stream',
                     'Syntax Error: Unknown marker segment in JPX tile-part stream', cleaned)
    cleaned: str = re.sub(r'Syntax Warning: Could not parse ligature component \"[^"]+\" of \"[^"]+\" in parseCharName',
                          'Syntax Warning: Could not parse ligature component in parseCharName', cleaned)

    return cleaned

def _pdftocairo_clean_message(err):
    cleaned = re.sub(r'\([\d]+\)', '', err)
    cleaned = re.sub(r'<[\w]{2}>', '', cleaned)
    cleaned = re.sub(r"\'[^']+\'", "\'x\'", cleaned)
    cleaned = re.sub(r'\([^)]+\)', "\'x\'", cleaned)
    cleaned = re.sub(r'xref num [\d]+', "xref num \'x\'", cleaned)
    cleaned: str = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
        'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
    return cleaned