import locale
import re
import sys

from typing import Dict, Any

from pdfminer.high_level import extract_text
from pdfminer.layout import LAParams

from pdfminer.pdfdocument import PDFDocument, PDFXRef, PDFXRefFallback
from pdfminer.pdfparser import PDFParser
from pdfminer.pdftypes import PDFObjectNotFound
from pdfminer.pdftypes import PDFStream, PDFObjRef
from pdfminer.psparser import PSKeyword, PSLiteral
from pdfminer.utils import isnumber

from sparclur._text_extractor import TextExtractor
from sparclur._metadata_extractor import MetadataExtractor, METADATA_SUCCESS
from sparclur._parser import VALID, VALID_WARNINGS, REJECTED, REJECTED_AMBIG, META, TEXT


ESC_PAT = re.compile(r'[\000-\037&<>()"\042\047\134\177-\377]')


def e(s):
    if isinstance(s, bytes):
        s = str(s, 'latin-1')
    return ESC_PAT.sub(lambda m: '&#%d;' % ord(m.group(0)), s)


def _clean_xml_line(line):
    return ''.join(
        c for c in line if ord(c) > 0x1f and ord(c) != 0x7f and not (0x80 <= ord(c) <= 0x9f) and not ord(c) == 0xa0)


def _extract_atomic(o):
    if isinstance(o, dict):
        keys = list(o.keys())
        if keys.count('@size') > 0:
            if o['@size'] == '0':
                return []
        if keys.count('literal') > 0:
            return o['literal']
        elif keys.count('number') > 0:
            return o['number']
        elif keys.count('string') > 0:
            return _extract_atomic(o['string'])
        elif keys.count('@id') > 0:
            i = o['@id'] + ' 0 R'
            return i
        elif keys.count('ref') > 0:
            i = _extract_atomic(o['ref'])
            return i
        elif keys.count('value') > 0:
            og_values = o['value']
            new_values = _extract_atomic(og_values)
            og_keys = o['key']
            new_keys = _extract_atomic(og_keys)
            if o['@size'] == '1':
                new_o = [(new_keys, new_values)]
            else:
                new_o = [(k, v) for (k, v) in zip(new_keys, new_values)]
            return dict(new_o)
        elif keys.count('dict') > 0:
            return _extract_atomic(o['dict'])
        elif keys.count('list') > 0:
            list_contents = o['list']
            if isinstance(list_contents, dict):
                list_keys = [k for k in list(o['list'].keys()) if k != '@size']
                result = []
                for k in list_keys:
                    val = dict()
                    val.update({k: o['list'][k]})
                    ex_k = _extract_atomic(val)
                    if isinstance(ex_k, list):
                        result += ex_k
                    else:
                        result.append(ex_k)
                return result
            else:
                return _extract_atomic(o['list'])
        elif keys.count('#text') > 0:
            return o['#text']
        return o
    elif isinstance(o, list):
        atomics = [_extract_atomic(obj) for obj in o]
        return atomics
    elif o == None:
        return 'None'
    else:
        return o

def _parse_object(obj):
    keys = list(obj.keys())
    if keys.count('@id') > 0:
        raw_ref = obj['@id']
        object_name = raw_ref + ' 0 R'
        if keys.count('dict') > 0:
            contents = obj['dict']
        elif keys.count('list') > 0:
            contents = dict()
            contents.update({'list': obj['list']})
        elif keys.count('stream') > 0:
            contents = obj['stream']['props']
        else:
            present_keys = [key for key in keys if key != '@id']
            contents = dict()
            for key in present_keys:
                contents.update({key: obj[key]})
        parsed_contents = _extract_atomic(contents)
        if not (isinstance(parsed_contents, list) or isinstance(parsed_contents, dict)):
            parsed_contents = [parsed_contents]
        return (object_name, parsed_contents)
    elif keys.count('trailer') > 0:
        object_name = 'trailer'
        contents = obj['trailer']
        parsed_contents = _extract_atomic(contents)
        return (object_name, parsed_contents)


class PDFMiner(TextExtractor, MetadataExtractor):
    """PDFMiner Text Extraction"""

    def __init__(self, doc_path: str,
                 skip_check: bool = False,
                 page_delimiter: str = '\x0c',
                 detect_vertical: bool = False,
                 all_texts: bool = False,
                 stream_output: str = None):
        super().__init__(doc_path=doc_path, skip_check=skip_check)
        self._page_delimiter = page_delimiter
        self._detect_vertical = detect_vertical
        self._all_texts = all_texts
        self._laparams = LAParams(detect_vertical=self._detect_vertical, all_texts=self._all_texts)
        self._stream_output = stream_output if stream_output in ['text', 'raw', 'binary'] else None

    def _check_for_pdfminer(self) -> bool:
        return "pdfminer" in sys.modules.keys()

    def _check_for_text_extraction(self) -> bool:
        if self._can_extract is None:
            pdfminer_present = self._check_for_pdfminer()
            self._can_extract = pdfminer_present
            self._can_meta_extract = pdfminer_present
        return self._can_extract

    def validate_text(self) -> Dict[str, Any]:
        if TEXT not in self._validity:
            validity_results = dict()
            decoder = locale.getpreferredencoding()
            try:
                _ = extract_text(self._doc_path, page_numbers=None, codec=decoder, laparams=self._laparams)
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

    def validate_metadata(self) -> Dict[str, Any]:
        if META not in self._validity:
            validity_results = dict()
            if self._metadata is None:
                self._extract_metadata()
            if self._metadata_result == METADATA_SUCCESS:
                validity_results['valid'] = True
                validity_results['status'] = VALID
            else:
                validity_results['valid'] = False
                validity_results['status'] = REJECTED
                validity_results['info'] = self._metadata_result

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
        try:
            text = extract_text(self._doc_path, page_numbers=page_numbers, codec=decoder, laparams=self._laparams)
        except Exception as e:
            print(e)
            text = self._text = dict()
        return text

    def _extract_metadata(self):

        try:
            self._dumppdf()
            self._metadata_result = METADATA_SUCCESS
        except Exception as e:
            self._metadata = dict()
            self._metadata_result = str(e)

    def _dumppdf(self):
        fp = open(self._doc_path, 'rb')
        parser = PDFParser(fp)
        doc = PDFDocument(parser, '')
        self._metadata = dict()
        self._dumpallobjs(doc)
        return

    def _dumpallobjs(self, doc):
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
                    self.metadata['%i 0 R' % objid] = self._parseobj(obj)
                except PDFObjectNotFound as error:
                    print('not found: %r' % error)
        self.metadata['trailer'] = self._parsetrailers(doc)
        return

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
            # return e(obj)
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
