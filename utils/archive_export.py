"""Readable local archive exports; DM notes are never sent to connected players."""
from datetime import datetime
from pathlib import Path
import uuid
from xml.sax.saxutils import escape

from utils.paths import get_user_saves_dir, resource_path
from utils.session_archive import NOTE_FIELDS
from utils.storage import _check_chain


def sections(archive, sid):
    session = archive.get(sid)
    yield 'title', session['title']
    yield 'body', f"Kampagne: {session['campaign']}\nBeginn: {session['started']}\nEnde: {session['ended'] or 'Noch nicht abgeschlossen'}\nSpieler: {', '.join(session['participants']) or 'Keine Spieler erfasst'}"
    yield 'body', 'Dieses Journal enthält App-Ereignisse und DM-Notizen. Gespräche und Erzählungen werden nicht automatisch aufgenommen.'
    for key, label in NOTE_FIELDS.items():
        yield 'heading', label
        yield 'body', session['notes'].get(key) or 'Keine Notizen.'
    yield 'heading', 'Vollständiges Ereignisjournal'
    for event in archive.iter_events(sid):
        yield 'event', f"{event['time']} | {event['actor']} | {event['kind']}\n{event['message']}"


def export_archive(archive, sid, kind):
    if kind not in ('txt', 'pdf'):
        raise ValueError('Unbekanntes Exportformat.')
    folder = Path(get_user_saves_dir('archive')) / 'Exporte'
    _check_chain(folder)
    folder.mkdir(exist_ok=True)
    target = folder / f'Sitzungsprotokoll-{datetime.now():%Y%m%d-%H%M%S}-{uuid.uuid4().hex[:12]}.{kind}'
    temporary = target.with_suffix('.part')
    try:
        if kind == 'txt':
            with temporary.open('x', encoding='utf-8') as stream:
                for style, value in sections(archive, sid):
                    stream.write(value + '\n\n')
        else:
            _pdf(archive, sid, temporary)
        temporary.replace(target)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return target


def _pdf(archive, sid, target):
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.lib.colors import HexColor
    from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
    pdfmetrics.registerFont(TTFont('ArchiveFont', resource_path('assets/fonts/Vera.ttf')))
    body = ParagraphStyle('Body', fontName='ArchiveFont', fontSize=9, leading=13, spaceAfter=8,
                          textColor=HexColor('#283443'), splitLongWords=True)
    styles = {
        'body': body, 'event': body,
        'title': ParagraphStyle('Title', parent=body, fontSize=22, leading=28, spaceAfter=18),
        'heading': ParagraphStyle('Heading', parent=body, fontSize=13, leading=18, spaceBefore=12, spaceAfter=8, keepWithNext=True)}
    story = []
    for style, value in sections(archive, sid):
        # Short paragraphs also keep arbitrarily long user notes and journal entries splittable.
        chunks = [value[i:i+3000] for i in range(0, len(value), 3000)] or ['']
        for chunk in chunks:
            story.append(Paragraph(escape(chunk).replace('\n', '<br/>'), styles[style]))
    def footer(canvas, doc):
        canvas.saveState()
        canvas.setFont('ArchiveFont', 8)
        canvas.setFillColor(HexColor('#667080'))
        canvas.drawString(42, 27, 'DnD Lokal | Privates Sitzungsarchiv')
        canvas.drawRightString(A4[0]-42, 27, f'Seite {doc.page}')
        canvas.restoreState()
    doc = SimpleDocTemplate(str(target), pagesize=A4, rightMargin=42, leftMargin=42, topMargin=42,
                            bottomMargin=48, title=archive.get(sid)['title'], author='DnD Lokal')
    doc.build(story, onFirstPage=footer, onLaterPages=footer)
