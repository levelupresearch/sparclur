from sparclur.parsers._renderer import Renderer
import ghostscript

import locale
import tempfile
import os
import re

from PIL import Image


class GhostScript(Renderer):

    def __init__(self):
        self.name = 'GhostScript'

    def get_name(self):
        return self.name

    def render_page(self, path, page, dpi=200, size=None, temp_folders_dir=None):

        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as tmpdir:
            args = ["-dSAFER",
                    "-dBATCH",
                    "-dUseCropBox",
                    "-dNOPAUSE",
                    "-sDEVICE=png16m",
                    "-dTextAlphaBits=4",
                    "-dFirstPage="+str(page - 1),
                    "-dLastPage="+str(page - 1),
                    "-r"+str(dpi)
                    ]

            if size is not None:
                if isinstance(size, tuple):
                    size_arg = "-g%sx%s" % (str(size[0]), str(size[1]))
                else:
                    size_arg = "-g%sx%s" % (str(size), str(size))
                args.append(size_arg)

            args.append("-sOutputFile="+os.path.join(tmpdir, "out.png"))
            args.append(path)

            encoding = locale.getpreferredencoding()
            args = [arg.encode(encoding) for arg in args]
            gs = ghostscript.GhostScript(*args)

            pil = Image.open(os.path.join(tmpdir, "out.png"))
            gs.exit()
            ghostscript.cleanup()
        return pil

    def render_doc(self, path, dpi=200, size=None, temp_folders_dir=None):

        with tempfile.TemporaryDirectory(dir=temp_folders_dir) as tmpdir:
            args = ["-dSAFER",
                    "-dBATCH",
                    "-dUseCropBox",
                    "-dNOPAUSE",
                    "-sDEVICE=png16m",
                    "-dTextAlphaBits=4",
                    "-r"+str(dpi)
                    ]

            if size is not None:
                if isinstance(size, tuple):
                    size_arg = "-g%sx%s" % (str(size[0]), str(size[1]))
                else:
                    size_arg = "-g%sx%s" % (str(size), str(size))
                args.append(size_arg)

            args.append("-sOutputFile="+os.path.join(tmpdir, "page-%04d.png"))
            args.append(path)

            encoding = locale.getpreferredencoding()
            args = [arg.encode(encoding) for arg in args]
            gs = ghostscript.GhostScript(*args)

            pages = [int(re.sub('.png', '', re.sub('page-', '', file))) for file in os.listdir(tmpdir) if file.endswith('.png')]
            num_pages = max(pages) if len(pages) > 0 else 0
            pils = [None for file in range(num_pages)]
            for i in range(num_pages):
                try:
                    pil = Image.open(os.path.join(tmpdir, 'page-%s.png' % str(i).rjust(4, '0')))
                except:
                    pil = None
                pils[i] = pil
            gs.exit()
            ghostscript.cleanup()
            return pils
