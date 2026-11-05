"""Local resume rendering; never sends documents to an external service."""
from io import BytesIO
from pathlib import Path
import shutil
import subprocess
import tempfile
from PIL import Image, UnidentifiedImageError

MAX_PIXELS = 20_000_000
MAX_BYTES = 10 * 1024 * 1024


def render_resume(content: bytes, filename: str) -> bytes:
    suffix = Path(filename).suffix.lower()
    if suffix not in {'.png', '.jpg', '.jpeg', '.webp', '.pdf', '.doc', '.docx'}:
        raise ValueError('支持 PNG、JPG、WebP、PDF、DOC 和 DOCX 文件')
    if not content:
        raise ValueError('文件为空')
    with tempfile.TemporaryDirectory(prefix='getjobs-resume-') as folder:
        root = Path(folder)
        if suffix in {'.doc', '.docx'}:
            if suffix == '.docx':
                import zipfile
                try:
                    with zipfile.ZipFile(BytesIO(content)) as archive:
                        if 'word/document.xml' not in archive.namelist() or sum(i.file_size for i in archive.infolist()) > 50 * 1024 * 1024:
                            raise ValueError('Word 文件无效或解压后过大')
                except zipfile.BadZipFile as exc:
                    raise ValueError('无法读取 DOCX 文件') from exc
            elif not content.startswith(bytes.fromhex('d0cf11e0a1b11ae1')):
                raise ValueError('无法读取 DOC 文件，请导出为 PDF 后重试')
            executable = shutil.which('soffice')
            if not executable:
                raise ValueError('Word 转换需要安装 LibreOffice；也可以先将 Word 导出为 PDF 再上传')
            source = root / ('resume' + suffix)
            source.write_bytes(content)
            try:
                result = subprocess.run(
                    [executable, '-env:UserInstallation=' + (root / 'profile').as_uri(),
                     '--headless', '--convert-to', 'pdf', '--outdir', str(root), str(source)],
                    capture_output=True, timeout=60,
                )
            except subprocess.TimeoutExpired as exc:
                raise ValueError('Word 转换超时，请导出为 PDF 后重试') from exc
            pdf = root / 'resume.pdf'
            if result.returncode or not pdf.is_file():
                raise ValueError('无法转换 Word 文档，请检查文件是否损坏或加密，或导出为 PDF 后重试')
            content = pdf.read_bytes()
            suffix = '.pdf'
        if suffix == '.pdf':
            image = render_pdf(content)
        else:
            try:
                with Image.open(BytesIO(content)) as source:
                    if source.format not in {'PNG', 'JPEG', 'WEBP'} or source.width * source.height > MAX_PIXELS:
                        raise ValueError('图片格式或尺寸无效')
                    source.load()
                    image = Image.new('RGB', source.size, 'white')
                    rgba = source.convert('RGBA')
                    image.paste(rgba, mask=rgba.getchannel('A'))
            except (UnidentifiedImageError, OSError, Image.DecompressionBombError) as exc:
                raise ValueError('无法读取图片或图片尺寸过大') from exc
        try:
            output = BytesIO()
            image.save(output, format='PNG')
            if output.tell() > MAX_BYTES:
                raise ValueError('转换后的图片超过 10MB，请精简文档后重试')
            return output.getvalue()
        finally:
            image.close()


def render_pdf(content: bytes) -> Image.Image:
    import pypdfium2 as pdfium
    pages = []
    try:
        with pdfium.PdfDocument(content) as document:
            if not 1 <= len(document) <= 5:
                raise ValueError('简历文档需为 1–5 页；多页将按顺序拼成长图')
            sizes = []
            for index in range(len(document)):
                page = document[index]
                try:
                    width, height = page.get_size()
                    if width <= 0 or height <= 0:
                        raise ValueError('PDF 页面尺寸无效')
                    sizes.append((width, height))
                finally:
                    page.close()
            # Fixed readable width; reject excessive lengths rather than silently shrink text.
            height = sum(int(h * 1440 / w) + 1 for w, h in sizes)
            if height * 1440 > MAX_PIXELS:
                raise ValueError('文档页面过长，请精简内容后重试')
            for index, (width, _) in enumerate(sizes):
                page = document[index]
                bitmap = None
                try:
                    bitmap = page.render(scale=1440 / width)
                    pages.append(bitmap.to_pil().convert('RGB'))
                finally:
                    if bitmap is not None:
                        bitmap.close()
                    page.close()
            result = Image.new('RGB', (max(p.width for p in pages), sum(p.height for p in pages)), 'white')
            top = 0
            for page in pages:
                result.paste(page, (0, top))
                top += page.height
            return result
    except pdfium.PdfiumError as exc:
        raise ValueError('无法读取 PDF，请检查文件是否损坏或受密码保护') from exc
    finally:
        for page in pages:
            page.close()
