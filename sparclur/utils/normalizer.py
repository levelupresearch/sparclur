import re


def clean_messages(parser, messages):
    if isinstance(messages, str):
        messages = [messages]
    return [clean_error(parser, message) for message in messages]


def clean_error(parser, err):
    if parser == 'cairo':
        return clean_cairo(err)
    elif parser == 'qpdf':
        return clean_qpdf(err)
    # elif parser == 'pdfminer':
    #     return clean_pdfminer(err)
    elif parser.startswith('mutool'):
        return clean_mupdf(err)
    elif parser == 'pdftoppm':
        return clean_pdftoppm(err)


def clean_cairo(err):
    cleaned = re.sub(r'\([\d]+\)', '', err)
    cleaned = re.sub(r'<[\w]{2}>', '', cleaned)
    cleaned = re.sub(r"\'[^']+\'", "\'x\'", cleaned)
    cleaned = re.sub(r'\([^)]+\)', "\'x\'", cleaned)
    cleaned = re.sub(r'xref num [\d]+', "xref num \'x\'", cleaned)
    cleaned = 'Syntax Error: Unknown character collection Adobe-Identity' if cleaned.startswith(
        'Syntax Error: Unknown character collection Adobe-Identity') else cleaned
    return cleaned


def clean_qpdf(err):
    split_attempt = err.split(': ')
    if len(split_attempt) == 4:
        err = split_attempt[2] + ' ' + split_attempt[3]
    elif len(split_attempt) == 3:
        err = split_attempt[0] + ': ' + split_attempt[-1]
    else:
        err = split_attempt[-1]
    cleaned = re.sub(r'recovered stream length [\d]+', 'recovered stream length', err)
    cleaned = re.sub(r'object [\d]+ [\d+]', 'object', cleaned)
    cleaned = re.sub(r" \(obj=[\d]+\)", "", cleaned)
    cleaned = re.sub(r'converting [\d]+ ', "converting bigint ", cleaned)
    cleaned = re.sub(r' /QPDFFake[\d]+', "", cleaned)
    cleaned = re.sub(r'\([^)]*\)\s{0, 1}', "", cleaned)
    cleaned = re.sub(r' [\d]+ [\d]+ obj\s{0, 1}', ' something else ', cleaned)
    return cleaned


def clean_mupdf(err):
    cleaned = re.sub(r'\([\d]+ [\d]+ R\)', '', err)
    cleaned = re.sub(r'[\d]+ [\d]+ R', '', cleaned)
    cleaned = re.sub(r"\'[^']+\'", '', cleaned)
    cleaned = 'error: expected generation number' if cleaned.startswith(
        'error: expected generation number ') else cleaned
    cleaned = 'error: unknown colorspace' if cleaned.startswith('error: unknown colorspace: ') else cleaned
    cleaned = 'warning: non-embedded font using identity encoding' if cleaned.startswith(
        'warning: non-embedded font using identity encoding: ') else cleaned
    cleaned = re.sub(r'\(gid [\d]+\)', '', cleaned)
    cleaned = 'error: expected  keyword' if cleaned.startswith('error: expected  keyword ') else cleaned
    cleaned = 'warning: unknown filter name' if cleaned.startswith('warning: unknown filter name ') else cleaned
    cleaned = 'error: aes padding out of range' if cleaned.startswith('error: aes padding out of range:') else cleaned
    cleaned = 'error: cannot authenticate password' if cleaned.startswith(
        'error: cannot authenticate password:') else cleaned
    cleaned = re.sub(r'\[\d+\] prec\(\d+\) sgnd\(\d+\) \[\d+\] prec\(\d+\) sgnd\(\d+\)', 'Out of Memory Error', cleaned)
    cleaned = 'warning: cannot load content stream part' if cleaned.startswith(
        'warning: cannot load content stream part') else cleaned
    cleaned = 'error: object out of range' if cleaned.startswith('error: object out of range') else cleaned
    cleaned = 'warning: object out of range' if cleaned.startswith('warning: object out of range') else cleaned
    cleaned = 'error: object id  out of range' if cleaned.startswith('error: object id  out of range') else cleaned
    cleaned = re.sub(r"\'\'", '', cleaned)
    cleaned = 'error: invalid reference to non-object-stream' if cleaned.startswith(
        'error: invalid reference to non-object-stream:') else cleaned
    cleaned = 'error: object offset out of range' if cleaned.startswith(
        'error: object offset out of range:') else cleaned
    cleaned = 'error: unexpected xref type' if cleaned.startswith('error: unexpected xref type:') else cleaned
    cleaned = 'error: unknown keyword' if cleaned.startswith('error: unknown keyword:') else cleaned
    cleaned = re.sub(r'warning: Encountered new definition for object \d+ - keeping the original one',
                     'warning: Encountered new definition for object - keeping the original one', cleaned)
    cleaned = 'warning: bf_range limits out of range in cmap' if cleaned.startswith(
        'warning: bf_range limits out of range in cmap') else cleaned
    cleaned = 'warning: ignoring one to many mapping in cmap' if cleaned.startswith(
        'warning: ignoring one to many mapping in cmap') else cleaned
    cleaned = re.sub(r'\(segment [\-]?\d+\)', '', cleaned)
    cleaned = re.sub(r'\([\-]?\d+\)', '', cleaned)
    cleaned = re.sub(r'\(\d+\/\d+\)', '', cleaned)
    cleaned = 'warning: jbig2dec error: Invalid SYMWIDTH value' if cleaned.startswith(
        'warning: jbig2dec error: Invalid SYMWIDTH value') else cleaned
    cleaned = 'warning: jbig2dec error: No OOB signalling end of height class' if cleaned.startswith(
        'warning: jbig2dec error: No OOB signalling end of height class') else cleaned
    cleaned = 'warning: openjpeg error: Failed to decode tile' if cleaned.startswith(
        'warning: openjpeg error: Failed to decode tile') else cleaned
    cleaned = 'warning: openjpeg error: Invalid component index' if cleaned.startswith(
        'warning: openjpeg error: Invalid component index') else cleaned
    cleaned = 'warning: openjpeg error: Invalid tile part index for tile number' if cleaned.startswith(
        'warning: openjpeg error: Invalid tile part index for tile number') else cleaned
    cleaned = re.sub(
        r'warning: openjpeg error: Invalid values for comp = \d+ : prec=\d+ (should be between 1 and 38 according to the JPEG2000 norm. OpenJpeg only supports up to 31)',
        'warning: openjpeg error: Invalid values for comp = x : prec=y (should be between 1 and 38 according to the JPEG2000 norm. OpenJpeg only supports up to 31)',
        cleaned)
    cleaned = 'warning: openjpeg error: read: segment too long  with max  for codeblock' if cleaned.startswith(
        'warning: openjpeg error: read: segment too long  with max  for codeblock') else cleaned
    cleaned = re.sub(r'comp\[\d+\]', 'comp', cleaned)
    cleaned = re.sub(r'\[\d+\] prec\(\d+\) sgnd\(\d+\) \[\d+\] prec\(\d+\) sgnd\(\d+\)', 'Out of Memory Error', cleaned)

    return cleaned

# PLACEHOLDER
# def clean_pdfminer(err):
#     cleaned = err
#     return cleaned


def clean_pdftoppm(err):
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
    cleaned = 'Syntax Error: Invalid XRef entry' if cleaned.startswith('Syntax Error: Invalid XRef entry') else cleaned
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
    cleaned = re.sub(r'Syntax Warning: Could not parse ligature component \"[^"]+\" of \"[^"]+\" in parseCharName',
                     'Syntax Warning: Could not parse ligature component in parseCharName', cleaned)

    return cleaned
