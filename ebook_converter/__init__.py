import html
import logging
import math
import mimetypes
import os
import pkg_resources
import re
import sys

from functools import partial

from ebook_converter import constants_old
from ebook_converter.constants_old import \
    __appname__, __version__, __author__, \
    config_dir
from ebook_converter.ebooks.html_entities import html5_entities


if False:
    # Prevent pyflakes from complaining
    __appname__, __version__, __author__, config_dir


def init_mimetypes():
    mimetypes.init([pkg_resources.resource_filename('ebook_converter',
                                                    'data/mime.types')])


def guess_extension(*args, **kwargs):
    ext = mimetypes.guess_extension(*args, **kwargs)
    if not ext and args and args[0] == 'application/x-palmreader':
        ext = '.pdb'
    return ext


def sanitize_file_name(name, substitute='_'):
    """
    Sanitize the filename `name`. All invalid characters are replaced by
    `substitute`. The set of invalid characters is the union of the invalid
    characters in Windows, macOS and Linux. Also removes leading and trailing
    whitespace.

    **WARNING:** This function also replaces path separators, so only pass
    file names and not full paths to it.
    """

    if isinstance(name, bytes):
        name = name.decode(constants_old.filesystem_encoding, 'replace')
    if isinstance(substitute, bytes):
        substitute = substitute.decode(constants_old.filesystem_encoding,
                                       'replace')
    chars = (substitute
             if c in set(('\\', '|', '?', '*', '<', '"', ':', '>', '+', '/') +
                         tuple(map(chr, range(32)))) else c for c in name)
    one = ''.join(chars)
    one = re.sub(r'\s', ' ', one).strip()
    bname, ext = os.path.splitext(one)
    one = re.sub(r'^\.+$', '_', bname)
    one = one.replace('..', substitute)
    one += ext
    # Windows doesn't like path components that end with a period or space
    if one and one[-1] in ('.', ' '):
        one = one[:-1]+'_'
    # Names starting with a period are hidden on Unix
    if one.startswith('.'):
        one = '_' + one[1:]
    return one


def setup_cli_handlers(logger, level):
    if os.getenv('CALIBRE_WORKER') and logger.handlers:
        return
    logger.setLevel(level)
    if level == logging.WARNING:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter('%(levelname)s: %(message)s'))
        handler.setLevel(logging.WARNING)
    elif level == logging.INFO:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter())
        handler.setLevel(logging.INFO)
    elif level == logging.DEBUG:
        handler = logging.StreamHandler(sys.stderr)
        handler.setLevel(logging.DEBUG)
        handler.setFormatter(logging.Formatter('[%(levelname)s] %(filename)s:'
                                               '%(lineno)s: %(message)s'))

    logger.addHandler(handler)


def fit_image(width, height, pwidth, pheight):
    """
    Fit image in box of width pwidth and height pheight.
    @param width: Width of image
    @param height: Height of image
    @param pwidth: Width of box
    @param pheight: Height of box
    @return: scaled, new_width, new_height. scaled is True iff new_width
             and/or new_height is different from width or height.
    """
    scaled = height > pheight or width > pwidth
    if height > pheight:
        corrf = pheight / float(height)
        width, height = math.floor(corrf*width), pheight
    if width > pwidth:
        corrf = pwidth / float(width)
        width, height = pwidth, math.floor(corrf*height)
    if height > pheight:
        corrf = pheight / float(height)
        width, height = math.floor(corrf*width), pheight

    return scaled, int(width), int(height)


class CurrentDir(object):

    def __init__(self, path):
        self.path = path
        self.cwd = None

    def __enter__(self, *args):
        self.cwd = os.getcwd()
        os.chdir(self.path)
        return self.cwd

    def __exit__(self, *args):
        try:
            os.chdir(self.cwd)
        except EnvironmentError:
            # The previous CWD no longer exists
            pass


def walk(dir):
    """A nice interface to os.walk"""
    for record in os.walk(dir):
        for f in record[-1]:
            yield os.path.join(record[0], f)


def my_unichr(num):
    try:
        return chr(num)
    except (ValueError, OverflowError):
        return '?'


def entity_to_unicode(match, exceptions=[], encoding='cp1252',
                      result_exceptions={}):
    """
    :param match: A match object such that '&'+match.group(1)';' is the entity.

    :param exceptions: A list of entities to not convert (Each entry is the
                       name of the entity, for e.g. 'apos' or '#1234'

    :param encoding: The encoding to use to decode numeric entities between
                     128 and 256. If None, the Unicode UCS encoding is used.
                     A common encoding is cp1252.

    :param result_exceptions: A mapping of characters to entities. If the
                              result is in result_exceptions,
                              result_exception[result] is returned instead.
                              Convenient way to specify exception for things
                              like < or > that can be specified by various
                              actual entities.
    """

    def check(ch):
        return result_exceptions.get(ch, ch)

    ent = match.group(1)
    if ent in exceptions:
        return '&'+ent+';'
    # squot is generated by some broken CMS software
    if ent in {'apos', 'squot'}:
        return check("'")
    if ent == 'hellips':
        ent = 'hellip'
    if ent.startswith('#'):
        try:
            if ent[1] in ('x', 'X'):
                num = int(ent[2:], 16)
            else:
                num = int(ent[1:])
        except Exception:
            return '&'+ent+';'
        if encoding is None or num > 255:
            return check(my_unichr(num))
        try:
            return check(bytes(bytearray((num,))).decode(encoding))
        except UnicodeDecodeError:
            return check(my_unichr(num))
    try:
        return check(html5_entities[ent])
    except KeyError:
        pass
    try:
        return check(my_unichr(html.entities.name2codepoint[ent]))
    except KeyError:
        return '&'+ent+';'


_ent_pat = re.compile(r'&(\S+?);')
xml_entity_to_unicode = partial(entity_to_unicode,
                                result_exceptions={'"': '&quot;',
                                                   "'": '&apos;',
                                                   '<': '&lt;',
                                                   '>': '&gt;',
                                                   '&': '&amp;'})


def replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(entity_to_unicode, encoding=encoding), raw)


def xml_replace_entities(raw, encoding='cp1252'):
    return _ent_pat.sub(partial(xml_entity_to_unicode, encoding=encoding), raw)


def prepare_string_for_xml(raw, attribute=False):
    raw = _ent_pat.sub(entity_to_unicode, raw)
    raw = raw.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')
    if attribute:
        raw = raw.replace('"', '&quot;').replace("'", '&apos;')
    return raw


def force_unicode(obj, enc=constants_old.preferred_encoding):
    if isinstance(obj, bytes):
        try:
            obj = obj.decode(enc)
        except Exception:
            try:
                obj = obj.decode(constants_old.filesystem_encoding
                                 if enc == constants_old.preferred_encoding
                                 else constants_old.preferred_encoding)
            except Exception:
                try:
                    obj = obj.decode('utf-8')
                except Exception:
                    obj = repr(obj)
                    if isinstance(obj, bytes):
                        obj = obj.decode('utf-8')
    return obj


def human_readable(size, sep=' '):
    """ Convert a size in bytes into a human readable form """
    divisor, suffix = 1, "B"
    for i, candidate in enumerate(('B', 'KB', 'MB', 'GB', 'TB', 'PB', 'EB')):
        if size < (1 << ((i + 1) * 10)):
            divisor, suffix = (1 << (i * 10)), candidate
            break
    size = str(float(size)/divisor)
    if size.find(".") > -1:
        size = size[:size.find(".")+2]
    if size.endswith('.0'):
        size = size[:-2]
    return size + sep + suffix
