"""Build a Word report using the supplied cover; no inferred student identity."""
import argparse
import re
from pathlib import Path
from docx import Document
from docx.enum.section import WD_SECTION_START
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, Cm, RGBColor


def font(run, size=11, bold=None):
    run.font.name='Source Han Sans CN'
    run._element.get_or_add_rPr().rFonts.set(qn('w:eastAsia'),'Source Han Sans CN')
    run.font.size=Pt(size)
    run.font.color.rgb=RGBColor.from_string('222222')
    if bold is not None: run.bold=bold


def build(markdown, cover, output):
    doc=Document(cover)
    # Legacy DOC templates may not contain the standard heading/table styles.
    from copy import deepcopy
    defaults=Document()
    for name in ['Heading 1','Heading 2','Heading 3','Table Grid']:
        if name not in doc.styles:
            doc.styles.element.append(deepcopy(defaults.styles[name].element))
    title=markdown.read_text().splitlines()[0].lstrip('# ')
    doc.tables[0].cell(0,1).text=title
    doc.tables[1].cell(5,1).text='2026年11月6日'
    # Keep identity and group fields blank until supplied by the student.
    for t in doc.tables:
        for row in t.rows:
            row.height=Cm(1.0)
            for cell in row.cells:
                for p in cell.paragraphs:
                    p.paragraph_format.left_indent=Cm(0);p.paragraph_format.right_indent=Cm(0)
                    p.paragraph_format.line_spacing=1.1;p.paragraph_format.space_after=Pt(4);p.paragraph_format.space_before=Pt(4)
                    for r in p.runs: font(r,12)
    for p in doc.paragraphs:
        p.paragraph_format.space_after=Pt(0);p.paragraph_format.space_before=Pt(0)
        if not p.text and not p._p.findall('.//' + qn('w:drawing')):
            p.paragraph_format.line_spacing=Pt(8)
            for r in p.runs:font(r,6)
        elif '期末报告' in p.text:
            p.paragraph_format.space_before=Pt(65);p.paragraph_format.space_after=Pt(35)
            for r in p.runs:font(r,22,True)
    for s in doc.sections:
        for p in s.footer.paragraphs: p.clear()
    section=doc.add_section(WD_SECTION_START.NEW_PAGE)
    section.page_height=Cm(29.7);section.page_width=Cm(21)
    section.top_margin=Cm(2.2);section.bottom_margin=Cm(2.0);section.left_margin=Cm(2.3);section.right_margin=Cm(2.3)
    section.different_first_page_header_footer=False
    numbering=OxmlElement('w:pgNumType');numbering.set(qn('w:start'),'1');section._sectPr.append(numbering)
    section.header.is_linked_to_previous=False
    section.footer.is_linked_to_previous=False
    for p in section.header.paragraphs: p.clear()
    hp=section.header.paragraphs[0];hp.alignment=WD_ALIGN_PARAGRAPH.CENTER;font(hp.add_run('机器学习课程期末报告 · 岗位需求分析'),9)
    p=section.footer.paragraphs[0];p.clear();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
    field=OxmlElement('w:fldSimple');field.set(qn('w:instr'),'PAGE');p._p.append(field)
    normal=doc.styles['Normal'];normal.font.name='Source Han Sans CN';normal.font.size=Pt(10.5)
    normal.paragraph_format.line_spacing=1.35;normal.paragraph_format.space_after=Pt(5)
    for name,size in [('Heading 1',16),('Heading 2',13),('Heading 3',11.5)]:
        st=doc.styles[name];st.font.name='Source Han Sans CN';st.font.size=Pt(size);st.font.color.rgb=RGBColor.from_string('163C45')
        st.paragraph_format.space_before=Pt(12);st.paragraph_format.space_after=Pt(6)
    lines=markdown.read_text().splitlines();i=1
    while i<len(lines):
        line=lines[i].strip();i+=1
        if not line:continue
        if line.startswith('|'):
            table_lines=[line]
            while i<len(lines) and lines[i].strip().startswith('|'):
                table_lines.append(lines[i].strip());i+=1
            rows=[[c.strip() for c in s.strip('|').split('|')] for s in table_lines if not re.match(r'^\|\s*:?-',s)]
            table=doc.add_table(rows=1,cols=len(rows[0]));table.style='Table Grid'
            for j,c in enumerate(rows[0]):table.rows[0].cells[j].text=c
            header=OxmlElement('w:tblHeader');table.rows[0]._tr.get_or_add_trPr().append(header)
            for row in rows[1:]:
                cells=table.add_row().cells
                for j,c in enumerate(row):cells[j].text=c
            for n,row in enumerate(table.rows):
                for cell in row.cells:
                    for p in cell.paragraphs:
                        p.paragraph_format.space_after=Pt(4)
                        p.paragraph_format.keep_with_next=n<len(table.rows)-1
                        for r in p.runs:font(r,9,n==0)
                trPr=row._tr.get_or_add_trPr();no_split=OxmlElement('w:cantSplit');trPr.append(no_split)
            continue
        image=re.match(r'!\[(.*?)\]\((.*?)\)',line)
        if image:
            p=doc.add_paragraph();p.alignment=WD_ALIGN_PARAGRAPH.CENTER
            p.add_run().add_picture(str(markdown.parent/image[2]),width=Cm(16))
            p.paragraph_format.keep_with_next=True
            cap=doc.add_paragraph(image[1]);cap.alignment=WD_ALIGN_PARAGRAPH.CENTER
            for run in cap.runs:font(run,9)
            continue
        heading=re.match(r'^(#{2,4})\s+(.*)',line)
        if heading:
            level=len(heading[1])-1
            p=doc.add_heading(heading[2],level=level)
            if heading[2].startswith('附录'):p.paragraph_format.page_break_before=True
            for run in p.runs:font(run,16 if level==1 else 13,True)
        else:
            p=doc.add_paragraph(line)
            p.alignment=WD_ALIGN_PARAGRAPH.LEFT
            p.paragraph_format.widow_control=True
            for run in p.runs:font(run,10.5)
    doc.save(output)


def export_pdf(docx):
    import os
    import subprocess
    import tempfile
    import xml.etree.ElementTree as ET
    import pypdfium2 as pdfium
    with tempfile.TemporaryDirectory(prefix='job-report-') as tmp:
        root=Path(tmp)
        # LibreOffice's bundled fontconfig can omit system CJK font directories.
        config=ET.Element('fontconfig')
        for directory in ['/System/Library/Fonts',str(Path.home()/'Library/Fonts'),'/usr/share/fonts','/usr/local/share/fonts',str(Path.home()/'.local/share/fonts')]:
            if Path(directory).is_dir():ET.SubElement(config,'dir').text=directory
        ET.SubElement(config,'cachedir').text=str(root/'cache')
        path=root/'fonts.conf';ET.ElementTree(config).write(path,encoding='utf-8',xml_declaration=True)
        env={**os.environ,'FONTCONFIG_FILE':str(path)}
        subprocess.run(['soffice',f'-env:UserInstallation={(root/"profile").as_uri()}','--headless','--convert-to','pdf','--outdir',str(docx.parent),str(docx)],env=env,check=True,timeout=90)
        with pdfium.PdfDocument(docx.with_suffix('.pdf')) as document:
            text=''.join(p.get_textpage().get_text_range() for p in document)
            if len(re.findall(r'[\u4e00-\u9fff]',text))<1000:
                raise RuntimeError('PDF中文缺字，拒绝交付，请安装中文字体')
            print(f'PDF verified: {len(document)} pages, Chinese text present')


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--markdown',type=Path,required=True);p.add_argument('--cover',type=Path,required=True);p.add_argument('--output',type=Path,required=True)
    p.add_argument('--pdf',action='store_true')
    args=p.parse_args();build(args.markdown,args.cover,args.output)
    if args.pdf:export_pdf(args.output)
