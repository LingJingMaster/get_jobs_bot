from io import BytesIO
import shutil
import zipfile
import pytest
from PIL import Image
from backend.app.resume import render_resume


def pdf_bytes(count):
    pages = [Image.new('RGB', (100, 140), color) for color in ['red', 'blue'] * count]
    out = BytesIO()
    pages[0].save(out, 'PDF', save_all=True, append_images=pages[1:count])
    return out.getvalue()


def test_pdf_preserves_all_pages_in_order():
    result = Image.open(BytesIO(render_resume(pdf_bytes(2), 'resume.pdf')))
    assert result.width == 1440
    assert result.height >= 4000
    assert result.getpixel((10, 10))[0] > 200
    assert result.getpixel((10, result.height - 10))[2] > 200


def test_invalid_or_long_document():
    with pytest.raises(ValueError):
        render_resume(b'broken', 'resume.pdf')
    with pytest.raises(ValueError, match='1–5'):
        render_resume(pdf_bytes(6), 'resume.pdf')
    with pytest.raises(ValueError):
        render_resume(b'broken', 'resume.docx')


@pytest.mark.skipif(not shutil.which('soffice'), reason='LibreOffice is optional')
def test_real_word_conversion():
    output = BytesIO()
    with zipfile.ZipFile(output, 'w') as z:
        z.writestr('[Content_Types].xml', '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/></Types>')
        z.writestr('_rels/.rels', '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/></Relationships>')
        z.writestr('word/document.xml', '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:body><w:p><w:r><w:t>Resume conversion test 简历</w:t></w:r></w:p></w:body></w:document>')
    image = Image.open(BytesIO(render_resume(output.getvalue(), 'resume.docx')))
    assert image.format == 'PNG'
    assert image.width == 1440
