from PIL.Image import Image
from sparclur._hybrid import Hybrid
from sparclur._parser import Parser
from sparclur._parser import RENDER, TRACER, TEXT, FONT, IMAGE, META
import os, sys, site

# TEST_PDF = '../../../resources/hello_world_hand_edit.pdf'
os.chdir(os.path.dirname(os.path.realpath(__file__)))
_cloned_path = os.path.realpath('../resources/hello_world_hand_edit.pdf')
_user_path = os.path.join(site.USER_BASE, 'etc', 'sparclur', 'resources', 'hello_world_hand_edit.pdf')
_env_path = os.path.join(sys.prefix, 'etc', 'sparclur', 'resources', 'hello_world_hand_edit.pdf')
if os.path.isfile(_cloned_path):
    TEST_PDF = _cloned_path
elif os.path.isfile(_user_path):
    TEST_PDF = _user_path
elif os.path.isfile(_env_path):
    TEST_PDF = _env_path

class ParserTestMixin:

    def test_parser(self):
        assert issubclass(self.parser, Parser), "Not a parser"

    def test_get_name(self):
        assert isinstance(self.parser.get_name(), str), 'get_name() missing'

    def test_num_pages(self):
        assert isinstance(self.parser_instance.num_pages, int), 'num_pages broken'

    def test_parser_validity(self):
        assert isinstance(self.parser_instance.validity, dict), 'validity broken'


class TracerTestMixin:

    def test_can_trace(self):
        assert self.parser_instance.can_trace, 'Tracer broken'

    def test_tracer_validity(self):
        assert TRACER in self.parser_instance.validity, 'validate_tracer missing'

    def test_tracer_messages(self):
        messages = self.parser_instance.messages
        assert isinstance(messages, list)
        assert len(messages) > 0

    def test_tracer_normalization(self):
        cleaned = self.parser_instance.cleaned
        assert isinstance(cleaned, dict), 'normalized trace counts broken'
        assert len(cleaned) > 0


class RendererTestMixin:

    def test_can_render(self):
        assert self.parser_instance.can_render, 'Rendering broken'

    def test_renderer_validity(self):
        assert RENDER in self.parser_instance.validity, 'validate_renderer missing'

    def test_single_page_rendering(self):
        assert isinstance(self.parser_instance.get_renders(0), Image), 'rendering failed'

    def test_multi_page_rendering(self):
        multi_pil = self.parser_instance.get_renders([0])
        assert isinstance(multi_pil, dict), 'multi-page rendering failed'
        assert isinstance(multi_pil[0], Image), 'multi-page rendering empty'

    def test_document_rendering(self):
        document_pil = self.parser_instance.get_renders()
        assert isinstance(document_pil, dict), 'document rendering failed'
        assert isinstance(document_pil[0], Image), 'document rendering empty'

    def test_rendering_logs(self):
        _ = self.parser_instance.get_renders()
        assert isinstance(self.parser_instance.logs, dict) and 0 in self.parser_instance.logs, 'logging failed'

    def test_rendering_dpi(self):
        self.parser_instance.caching = False
        self.parser_instance.dpi = 72
        pil72 = self.parser_instance.get_renders(0)
        self.parser_instance.dpi = 200
        pil200 = self.parser_instance.get_renders(0)
        width72 = pil72.width
        height72 = pil72.height
        width200 = pil200.width
        height200 = pil200.height
        assert abs(width200 - (width72 * 200 / 72)) <= 1 and abs(height200 - (height72 * 200 / 72)) <=1

    def test_ocr(self):
        if issubclass(self.parser, Hybrid):
            self.parser_instance.ocr = True
        assert self.parser_instance.can_extract_text, 'ocr missing'


class ReforgerTestMixin:

    def test_can_reforge(self):
        assert self.parser_instance.can_reforge, 'Reforging broken'

    def test_reforge(self):
        try:
            _ = self.parser_instance.reforge
            result = True
        except Exception as e:
            result = False
        assert result, str(e)


class FontExtractorTestMixin:

    def test_can_extract_font(self):
        assert self.parser_instance.can_extract_font

    def test_font_extract_validity(self):
        assert FONT in self.parser_instance.validity

    def test_fonts(self):
        try:
            _ = self.parser_instance.fonts
            result = True
        except Exception as e:
            result = False
        assert result, str(e)


class ImageDataExtractorTestMixin:

    def test_can_extract_image_data(self):
        assert self.parser_instance.can_extract_image_data

    def test_image_data_extraction_validity(self):
        assert IMAGE in self.parser_instance.validity

    def test_image_data(self):
        try:
            _ = self.parser_instance.images
            result = True
        except Exception as e:
            result = False
        assert result, str(e)


class MetadataExtractorTestMixin:

    def test_can_extract_metadata(self):
        assert self.parser_instance.can_extract_metadata

    def test_metadata_extraction_validity(self):
        assert META in self.parser_instance.validity

    def test_metadata_extraction(self):
        try:
            _ = self.parser_instance.metadata
            result = True
        except Exception as e:
            result = False
        assert result, str(e)


class TextExtractorTestMixin:

    def test_can_extract_text(self):
        if isinstance(self.parser, Hybrid):
            self.parser.ocr = False
        assert self.parser_instance.can_extract_text

    def test_text_extraction_validity(self):
        assert TEXT in self.parser_instance.validity

    def test_single_page_extraction(self):
        assert isinstance(self.parser_instance.get_text(0), str)

    def test_document_extraction(self):
        document_pil = self.parser_instance.get_text()
        assert isinstance(document_pil, dict)
        assert isinstance(document_pil[0], str)
