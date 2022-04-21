import locale
import os
import sys
import tempfile

from typing import Dict, Any, List
import warnings

import yaml
from func_timeout import func_timeout, FunctionTimedOut
from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

from pdfminer.pdfdocument import PDFDocument, PDFXRef, PDFXRefFallback
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFObjectNotFound
from pdfminer.pdfinterp import resolve1
from pdfminer.pdftypes import PDFStream, PDFObjRef
from pdfminer.psparser import PSKeyword, PSLiteral
from pdfminer.utils import isnumber

from sparclur._text_extractor import TextExtractor
from sparclur._metadata_extractor import MetadataExtractor, METADATA_SUCCESS
from sparclur._parser import VALID, REJECTED, META, TEXT, TIMED_OUT
from sparclur.utils import hash_file
from sparclur.utils._config import _get_config_param, _load_config


class PDFMiner(TextExtractor, MetadataExtractor):
    """PDFMiner Text Extraction https://pdfminersix.readthedocs.io/en/latest/"""

    def __init__(self, doc: str or bytes,
                 temp_folders_dir: str = None,
                 skip_check: bool = None,
                 hash_exclude: str or List[str] = None,
                 timeout: int = None,
                 page_delimiter: str = None,
                 detect_vertical: bool = None,
                 all_texts: bool = None,
                 stream_output: str = None,
                 suppress_warnings: bool = None):
        """
        Parameters
        ----------
        page_delimiter: str
            Marks the end str that separates pages in pdftotext
        detect_vertical : bool
            Flag to detect vertically oriented text
        all_texts : bool
            If layout analysis should be performed on text in figures
        stream_output : {`None`, 'raw', 'text', 'binary'}
            `None` indicates that streams should not be returned in the metadata. 'raw' is the stream object without
            encoding. 'binary' is the stream object with binary encoding. 'text' is the stream as plain text.
        suppress_warnings : bool
            EXPERIMENTAL: Tries to suppress the messages that PDFMiner displays during parsing.
        """
        config = _load_config()
        temp_folders_dir = _get_config_param(PDFMiner, config, 'temp_folders_dir', temp_folders_dir, None)
        skip_check = _get_config_param(PDFMiner, config, 'skip_check', skip_check, False)
        hash_exclude = _get_config_param(PDFMiner, config, 'hash_exclude', hash_exclude, None)
        timeout = _get_config_param(PDFMiner, config, 'timeout', timeout, None)
        page_delimiter = _get_config_param(PDFMiner, config, 'page_delimiter', page_delimiter, '\x0c')
        detect_vertical = _get_config_param(PDFMiner, config, 'detect_vertical', detect_vertical, False)
        all_texts = _get_config_param(PDFMiner, config, 'all_texts', all_texts, False)
        stream_output = _get_config_param(PDFMiner, config, 'stream_output', stream_output, None)
        suppress_warnings = _get_config_param(PDFMiner, config, 'suppress_warnings', suppress_warnings, True)

        super().__init__(doc=doc,
                         temp_folders_dir=temp_folders_dir,
                         skip_check=skip_check,
                         timeout=timeout,
                         hash_exclude=hash_exclude)
        self._page_delimiter = page_delimiter
        self._detect_vertical = detect_vertical
        self._all_texts = all_texts
        self._laparams = LAParams(detect_vertical=self._detect_vertical, all_texts=self._all_texts)
        self._stream_output = stream_output if stream_output in ['text', 'raw', 'binary'] else None
        self._suppress_warnings = suppress_warnings
        self._decoder = locale.getpreferredencoding()
        if suppress_warnings:
            # pdflogs = [logging.getLogger(name) for name in logging.root.manager.loggerDict if name.startswith('pdfminer')]
            # for ll in pdflogs:
            #     ll.setLevel(logging.WARNING)
            # logging.getLogger('pdfminer').setLevel(logging.WARNING)
            # logging.propagate = False
            # logging.getLogger().setLevel(logging.ERROR)
            warnings.filterwarnings('ignore')

    def _check_for_pdfminer(self) -> bool:
        return "pdfminer" in sys.modules.keys()

    def _check_for_text_extraction(self) -> bool:
        if self._can_extract is None:
            pdfminer_present = self._check_for_pdfminer()
            self._can_extract = pdfminer_present
            self._can_meta_extract = pdfminer_present
        return self._can_extract

    def _get_num_pages(self):
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                file = open(doc_path, 'rb')
                parser = PDFParser(file)
                document = PDFDocument(parser)
                self._num_pages = int(resolve1(document.catalog['Pages'])['Count'])
            except:
                self._num_pages = 0
            finally:
                try:
                    file.close()
                except:
                    pass

    @property
    def validate_text(self) -> Dict[str, Any]:
        if TEXT not in self._validity:
            validity_results = dict()
            if self._file_timed_out.get(TEXT, False):
                validity_results['valid'] = False
                validity_results['status'] = TIMED_OUT
                validity_results['info'] = 'Timed Out: %i' % self._timeout
            else:
                with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
                    if isinstance(self._doc, bytes):
                        file_hash = hash_file(self._doc)
                        doc_path = os.path.join(temp_path, file_hash)
                        with open(doc_path, 'wb') as doc_out:
                            doc_out.write(self._doc)
                    else:
                        doc_path = self._doc
                    try:
                        _ = extract_text(doc_path, page_numbers=None, codec=self._decoder, laparams=self._laparams)
                        validity_results['valid'] = True
                        validity_results['status'] = VALID
                    except Exception as e:
                        validity_results['valid'] = False
                        validity_results['status'] = REJECTED
                        validity_results['info'] = str(e)
                    self._validity[TEXT] = validity_results
        return self._validity[TEXT]

    def _check_for_metadata(self) -> bool:
        if self._can_extract is None:
            pdfminer_present = self._check_for_pdfminer()
            self._can_extract = pdfminer_present
            self._can_meta_extract = pdfminer_present
        return self._can_meta_extract

    @property
    def validate_metadata(self) -> Dict[str, Any]:
        if META not in self._validity:
            validity_results = dict()
            if self._metadata is None:
                self._extract_metadata()
            if self._file_timed_out[META]:
                validity_results['valid'] = False
                validity_results['status'] = TIMED_OUT
                validity_results['info'] = 'Timed Out: %i' % self._timeout
            elif self._metadata_result == METADATA_SUCCESS:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = self._metadata_result
            self._validity[META] = validity_results
        return self._validity[META]

    @staticmethod
    def get_name():
        return 'PDFMiner'

    @property
    def stream_output(self):
        return self._stream_output

    @stream_output.setter
    def stream_output(self, so):
        assert so in ['text', 'raw', 'binary'], "Please select 'text', 'raw', or 'binary'"
        self._metadata = None
        self._stream_output = so

    @stream_output.deleter
    def stream_output(self):
        self._stream_output = None

    @property
    def page_delimiter(self):
        return self._page_delimiter

    @property
    def detect_vertical(self):
        return self._detect_vertical

    @detect_vertical.setter
    def detect_vertical(self, vert):
        self.clear_cache()
        self._detect_vertical = vert

    @property
    def all_texts(self):
        return self._all_texts

    @all_texts.setter
    def all_texts(self, at):
        self.clear_cache()
        self._all_texts = at

    def _extract_doc(self):
        text = self._pdfminer_text()
        if len(text) != 0:
            for (page, text) in enumerate(text.split(self._page_delimiter)[0:-1]):
                self._text[page] = text
        self._full_text_extracted = True

    def _extract_page(self, page: int):
        text = self._pdfminer_text(page=page)
        self._text[page] = text

    def _pdfminer_text(self, page=None):
        page_numbers = None if page is None else [page]
        decoder = locale.getpreferredencoding()
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            try:
                if self._timeout is None:
                    text = extract_text(doc_path, page_numbers=page_numbers, codec=decoder, laparams=self._laparams)
                else:
                    text = func_timeout(
                        self._timeout,
                        extract_text,
                        kwargs={
                            'pdf_file': doc_path,
                            'page_numbers': page_numbers,
                            'codec': decoder,
                            'laparams': self._laparams
                        }
                    )
                self._file_timed_out[TEXT] = False
            except FunctionTimedOut as e:
                print(e)
                self._text = dict()
                text = self._text
                self._file_timed_out[TEXT] = True
            except Exception as e:
                print(e)
                self._text = dict()
                text = self._text
                self._file_timed_out[TEXT] = False
            return text

    def _extract_metadata(self):
        try:
            if self._timeout is None:
                self._metadata = self._parsepdf()
            else:
                self._metadata = func_timeout(
                    self._timeout,
                    self._parsepdf
                )
            self._metadata_result = METADATA_SUCCESS
            self._file_timed_out[META] = False
        except FunctionTimedOut as e:
            self._metadata = dict()
            self._metadata_result = str(e)
            self._file_timed_out[META] = True
        except Exception as e:
            self._metadata = dict()
            self._metadata_result = str(e)
            self._file_timed_out[META] = False

    # The following functions were adapted from the PDFMiner dumppdf CLI:
    # https://github.com/euske/pdfminer/blob/master/tools/dumppdf.py

    def _parsepdf(self):
        with tempfile.TemporaryDirectory(dir=self._temp_folders_dir) as temp_path:
            if isinstance(self._doc, bytes):
                file_hash = hash_file(self._doc)
                doc_path = os.path.join(temp_path, file_hash)
                with open(doc_path, 'wb') as doc_out:
                    doc_out.write(self._doc)
            else:
                doc_path = self._doc
            fp = open(doc_path, 'rb')
            parser = PDFParser(fp)
            doc = PDFDocument(parser, '')
            metadata = dict()
            visited = set()
            for xref in doc.xrefs:
                for objid in xref.get_objids():
                    if objid in visited:
                        continue
                    visited.add(objid)
                    try:
                        obj = doc.getobj(objid)
                        if obj is None:
                            continue
                        metadata['%i 0 R' % objid] = self._parseobj(obj)
                    except PDFObjectNotFound as error:
                        if not self._suppress_warnings:
                            print('not found: %r' % error)
            metadata['trailer'] = self._parsetrailers(doc)
            fp.close()
        return metadata

    def _parseobj(self, obj):
        if obj is None:
            return "Null"

        if isinstance(obj, dict):
            parsed_obj = {k: self._parseobj(v) for (k, v) in obj.items()}
            return parsed_obj

        if isinstance(obj, list):
            parsed_obj = [self._parseobj(el) for el in obj]
            return parsed_obj

        if isinstance(obj, ((str,), bytes)):
            return obj.decode(locale.getpreferredencoding(), errors='ignore')

        if isinstance(obj, PDFStream):
            if self._stream_output == 'raw':
                return obj.get_rawdata()
            elif self._stream_output == 'binary':
                try:
                    data = obj.get_data()
                except Exception as e:
                    data = "Data retrieval failed: %s" % str(e)
                return data
            else:
                props = self._parseobj(obj.attrs)
                if self._stream_output == 'text':
                    try:
                        data = obj.get_data()
                        props['Data'] = data.decode(locale.getpreferredencoding(), errors='ignore')
                    except Exception as e:
                        props['Data'] = "Data retrieval failed: %s" % str(e)
                return props

        if isinstance(obj, PDFObjRef):
            return '%i 0 R' % obj.objid

        if isinstance(obj, PSKeyword):
            return obj.name

        if isinstance(obj, PSLiteral):
            return obj.name

        if isnumber(obj):
            return obj

        raise TypeError(obj)

    def _parsetrailers(self, doc):
        if len(doc.xrefs) == 0:
            return "XRef not found"
        else:
            has_xref = False
            for xref in doc.xrefs:
                if isinstance(xref, PDFXRef) and not isinstance(xref, PDFXRefFallback):
                    has_xref = True
            if has_xref:
                return [self._parseobj(xref.trailer) for xref in doc.xrefs if not isinstance(xref, PDFXRefFallback)]
            else:
                return [self._parseobj(xref.trailer) for xref in doc.xrefs]
        # if len(pdfxref) == 1:
        #     return self._parseobj(pdfxref[0].trailer)
        # else:
        #     fallback = [xref for xref in doc.xrefs if isinstance(xref, PDFXRefFallback)]
        #     if len(fallback) == 0:
        #         return "XRef not found"
        #     else:
        #         return self._parseobj(fallback[0].trailer)
