# cv_generator.py
# -------------------------------------------------------------
# SaaS MVP: Generador de CV en PDF (Flask + ReportLab)
# - Formulario web (HTML+CSS+JS) con bloques dinámicos (agregar/eliminar)
# - 4 plantillas: classic, twocol, minimal, modern
# - Foto por URL y QR opcional (a website/LinkedIn)
# - Stripe Checkout (suscripción Pro mensual/anual) + Webhook
# - Healthcheck
# -------------------------------------------------------------
from flask import Flask, request, make_response, render_template_string, jsonify, redirect
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate, SimpleDocTemplate, PageTemplate, Frame, Paragraph, Spacer,
    Table, TableStyle, Image, FrameBreak, KeepInFrame
)
from io import BytesIO
from datetime import datetime
import requests
import os

# ===== Opcional: QR =====
try:
    import qrcode
except Exception:
    qrcode = None

# ===== Stripe =====
import stripe
stripe.api_key = os.environ.get("STRIPE_SECRET_KEY", "")

PRICE_MONTHLY = os.environ.get("STRIPE_PRICE_PRO_MONTHLY", "")
PRICE_YEARLY  = os.environ.get("STRIPE_PRICE_PRO_YEARLY", "")
WEBHOOK_SECRET = os.environ.get("STRIPE_WEBHOOK_SECRET", "")  # ponlo cuando crees el webhook

app = Flask(__name__)

# ====================== UTILIDADES ======================

def build_styles(accent="#0b7285", mono=False):
    styles = getSampleStyleSheet()
    # base
    if "HeaderSmall" not in styles:
        styles.add(ParagraphStyle(name="HeaderSmall", fontSize=11, leading=14, textColor=colors.HexColor('#666666')))
    else:
        styles["HeaderSmall"].fontSize = 11; styles["HeaderSmall"].leading = 14; styles["HeaderSmall"].textColor = colors.HexColor('#666666')
    if "Body" not in styles:
        styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14))
    if "ListItem" not in styles:
        styles.add(ParagraphStyle(name="ListItem", fontSize=10, leading=14, leftIndent=12, bulletIndent=0))
    styles.add(ParagraphStyle(name="SidebarTitle", fontSize=11, leading=14, textColor=colors.HexColor(accent)))
    styles.add(ParagraphStyle(name="Sidebar", fontSize=9, leading=12, textColor=colors.HexColor('#333333')))

    name_color = '#111111' if mono else '#222222'
    section_color = '#111111' if mono else accent

    if 'Name' not in styles:
        styles.add(ParagraphStyle(name="Name", fontSize=20, leading=24, spaceAfter=6, textColor=colors.HexColor(name_color)))
    else:
        styles['Name'].fontSize = 20; styles['Name'].leading = 24; styles['Name'].spaceAfter = 6; styles['Name'].textColor = colors.HexColor(name_color)

    styles.add(ParagraphStyle(name="Section", fontSize=14, leading=18, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor(section_color)))
    return styles

def fetch_image_bytes(url: str) -> bytes | None:
    if not url:
        return None
    try:
        r = requests.get(url, timeout=10)
        if r.ok and r.content:
            return r.content
    except Exception:
        pass
    return None

def make_qr_flowable(text: str):
    if not text or qrcode is None:
        return None
    try:
        img = qrcode.make(text)
        buf = BytesIO(); img.save(buf, format='PNG'); buf.seek(0)
        return Image(buf, width=2.5*cm, height=2.5*cm)
    except Exception:
        return None

def lines_to_bullets(text: str):
    text = (text or '').replace(';', '\n')
    return [ln.strip() for ln in text.split('\n') if ln.strip()]

# ====================== COLECCIONES ======================

def collect_experiences(data: dict):
    titles  = request.form.getlist('exp_title')  or data.get('exp_title',  [])
    comps   = request.form.getlist('exp_company') or data.get('exp_company', [])
    dates   = request.form.getlist('exp_dates')   or data.get('exp_dates',   [])
    descs   = request.form.getlist('exp_desc')    or data.get('exp_desc',    [])
    L = max(len(titles), len(comps), len(dates), len(descs)) if any([titles, comps, dates, descs]) else 0
    out = []
    for i in range(L):
        t = (titles[i] if i < len(titles) else '').strip()
        c = (comps[i] if i < len(comps) else '').strip()
        d = (dates[i] if i < len(dates) else '').strip()
        ds = (descs[i] if i < len(descs) else '').strip()
        if any([t, c, d, ds]):
            out.append((t, c, d, ds))
    return out

def collect_education(data: dict):
    titles  = request.form.getlist('edu_title')  or data.get('edu_title',  [])
    schools = request.form.getlist('edu_school') or data.get('edu_school', [])
    dates   = request.form.getlist('edu_dates')  or data.get('edu_dates',  [])
    L = max(len(titles), len(schools), len(dates)) if any([titles, schools, dates]) else 0
    out = []
    for i in range(L):
        t = (titles[i] if i < len(titles) else '').strip()
        s = (schools[i] if i < len(schools) else '').strip()
        d = (dates[i] if i < len(dates) else '').strip()
        if any([t, s, d]):
            out.append((t, s, d))
    return out

def collect_skills(data: dict):
    skill_inputs = request.form.getlist('skill')
    if skill_inputs:
        return [s.strip() for s in skill_inputs if s.strip()]
    raw = (data.get('skills') or '')
    return [s.strip() for s in raw.split(',') if s.strip()]

# ====================== PDFs (4 PLANTILLAS) ======================

# ---- Clásica ----
def build_pdf_classic(data: dict, accent="#0b7285") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = build_styles(accent=accent)
    story = []

    story.append(Paragraph(data.get('full_name') or 'Nombre Apellido', styles['Name']))
    if data.get('role'): story.append(Paragraph(data['role'], styles['HeaderSmall']))
    contact_bits = [data.get(k, '').strip() for k in ('email','phone','city','website') if data.get(k, '').strip()]
    if contact_bits: story.append(Paragraph(" • ".join(contact_bits), styles['HeaderSmall']))
    story.append(Spacer(1, 10))

    side_items = []
    wb = fetch_image_bytes((data.get('photo_url') or '').strip())
    if wb:
        try: side_items.append(Image(BytesIO(wb), width=3*cm, height=3*cm))
        except Exception: pass
    qr = make_qr_flowable((data.get('website') or '').strip())
    if qr: side_items.append(qr)
    if side_items:
        t = Table([[KeepInFrame(3.2*cm, 6*cm, side_items, mode='shrink'), Paragraph('', styles['Body'])]], colWidths=[3.5*cm, None])
        t.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)]))
        story.append(t); story.append(Spacer(1,6))

    if data.get('summary'):
        story.append(Paragraph('Resumen', styles['Section']))
        story.append(Paragraph(data['summary'], styles['Body']))
        story.append(Spacer(1, 6))

    skills = collect_skills(data)
    if skills:
        story.append(Paragraph('Habilidades', styles['Section']))
        cols = 3 if len(skills) >= 9 else (2 if len(skills) >= 6 else 1)
        rows = []
        for i in range(0, len(skills), cols):
            row = skills[i:i+cols]
            while len(row) < cols: row.append('')
            rows.append(row)
        t = Table(rows, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#333333')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t); story.append(Spacer(1, 6))

    experiences = collect_experiences(data)
    if experiences:
        story.append(Paragraph('Experiencia', styles['Section']))
        for (title, company, dates, desc) in experiences:
            story.append(Paragraph(f"<b>{title or 'Puesto'}</b> — {company or ''} <font color='#666666'>({dates or ''})</font>", styles['Body']))
            for b in lines_to_bullets(desc):
                story.append(Paragraph(b, styles['ListItem'], bulletText='•'))
            story.append(Spacer(1, 4))

    edu_entries = collect_education(data)
    if edu_entries:
        story.append(Paragraph('Formación', styles['Section']))
        for (t_, s_, d_) in edu_entries:
            story.append(Paragraph(f"<b>{t_ or 'Título'}</b> — {s_ or ''} <font color='#666666'>({d_ or ''})</font>", styles['Body']))
        story.append(Spacer(1, 4))

    generated = datetime.now().strftime('%Y-%m-%d')
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<font size=8 color='#888888'>Generado con cv_generator.py · {generated}</font>", styles['Body']))

    doc.build(story)
    pdf = buffer.getvalue(); buffer.close(); return pdf

# ---- Dos columnas ----
def build_pdf_twocol(data: dict, accent="#0b7285") -> bytes:
    buffer = BytesIO()
    styles = build_styles(accent=accent)
    width, height = A4; margin = 1.8*cm; sidebar_w = 6.2*cm; gap = 0.6*cm
    main_w = width - (2*margin + sidebar_w + gap)

    frame_sidebar = Frame(margin, margin, sidebar_w, height-2*margin, id='sidebar')
    frame_main = Frame(margin+sidebar_w+gap, margin, main_w, height-2*margin, id='main')

    doc = BaseDocTemplate(buffer, pagesize=A4, leftMargin=margin, rightMargin=margin, topMargin=margin, bottomMargin=margin)
    doc.addPageTemplates([PageTemplate(id='TwoCol', frames=[frame_sidebar, frame_main])])

    story = []

    wb = fetch_image_bytes((data.get('photo_url') or '').strip())
    if wb:
        try: story.append(Image(BytesIO(wb), width=4.2*cm, height=4.2*cm)); story.append(Spacer(1, 6))
        except Exception: pass

    full_name = data.get('full_name', '').strip() or 'Nombre Apellido'
    role = (data.get('role') or '').strip()
    story.append(Paragraph(full_name, styles['SidebarTitle']))
    if role: story.append(Paragraph(role, styles['Sidebar']))
    story.append(Spacer(1, 4))

    contact_rows = []
    for label, key in (("Email","email"),("Tel.","phone"),("Ciudad","city"),("Web","website")):
        val = (data.get(key) or '').strip()
        if val:
            contact_rows.append([Paragraph(f"<b>{label}:</b>", styles['Sidebar']), Paragraph(val, styles['Sidebar'])])
    if contact_rows:
        t = Table(contact_rows, colWidths=[2.2*cm, None])
        t.setStyle(TableStyle([
            ('VALIGN',(0,0),(-1,-1),'TOP'),('BOTTOMPADDING',(0,0),(-1,-1),2),
            ('LEFTPADDING',(0,0),(-1,-1),0),('RIGHTPADDING',(0,0),(-1,-1),0)
        ]))
        story.append(t); story.append(Spacer(1, 6))

    skills = collect_skills(data)
    if skills:
        story.append(Paragraph('Habilidades', styles['SidebarTitle']))
        for s in skills: story.append(Paragraph(f"• {s}", styles['Sidebar']))
        story.append(Spacer(1, 6))

    qr = make_qr_flowable((data.get('website') or '').strip())
    if qr: story.append(Paragraph('Perfil', styles['SidebarTitle'])); story.append(qr); story.append(Spacer(1, 10))

    story.append(FrameBreak())

    if data.get('summary'):
        story.append(Paragraph('Resumen', styles['Section']))
        story.append(Paragraph(data['summary'], styles['Body']))
        story.append(Spacer(1, 6))

    experiences = collect_experiences(data)
    if experiences:
        story.append(Paragraph('Experiencia', styles['Section']))
        for (title, company, dates, desc) in experiences:
            story.append(Paragraph(f"<b>{title or 'Puesto'}</b> — {company or ''} <font color='#666666'>({dates or ''})</font>", styles['Body']))
            for b in lines_to_bullets(desc): story.append(Paragraph(b, styles['ListItem'], bulletText='•'))
            story.append(Spacer(1, 4))

    edu_entries = collect_education(data)
    if edu_entries:
        story.append(Paragraph('Formación', styles['Section']))
        for (t_, s_, d_) in edu_entries:
            story.append(Paragraph(f"<b>{t_ or 'Título'}</b> — {s_ or ''} <font color='#666666'>({d_ or ''})</font>", styles['Body']))
        story.append(Spacer(1, 4))

    generated = datetime.now().strftime('%Y-%m-%d')
    story.append(Spacer(1, 8)); story.append(Paragraph(f"<font size=8 color='#888888'>Generado · {generated}</font>", styles['Body']))

    doc.build(story)
    pdf = buffer.getvalue(); buffer.close(); return pdf

# ---- Minimal (monocromo) ----
def build_pdf_minimal(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = build_styles(accent="#000000", mono=True)
    story = []
    story.append(Paragraph((data.get('full_name') or 'Nombre Apellido').upper(), styles['Name']))
    if data.get('role'): story.append(Paragraph(data['role'], styles['HeaderSmall']))
    story.append(Spacer(1, 8))

    def hr():
        t = Table([[""]], colWidths=[None], rowHeights=[0.6])
        t.setStyle(TableStyle([('BACKGROUND',(0,0),(-1,-1),colors.black)]))
        story.append(t); story.append(Spacer(1,6))

    if data.get('summary'):
        story.append(Paragraph('RESUMEN', styles['Section']))
        story.append(Paragraph(data['summary'], styles['Body']))
        hr()

    skills = collect_skills(data)
    if skills:
        story.append(Paragraph('HABILIDADES', styles['Section']))
        story.append(Paragraph(" · ".join(skills), styles['Body']))
        hr()

    exps = collect_experiences(data)
    for title, company, dates, desc in exps:
        story.append(Paragraph(f"<b>{title}</b> — {company} {dates}", styles['Body']))
        for b in lines_to_bullets(desc): story.append(Paragraph(b, styles['ListItem'], bulletText='–'))
    if exps: hr()

    for t_, s_, d_ in collect_education(data):
        story.append(Paragraph(f"<b>{t_}</b> — {s_} {d_}", styles['Body']))

    doc.build(story)
    pdf = buffer.getvalue(); buffer.close(); return pdf

# ---- Modern (barra superior a color) ----
def build_pdf_modern(data: dict, accent="#2563eb") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)
    styles = build_styles(accent=accent)
    story = []

    head = Table([[Paragraph(data.get('full_name') or 'Nombre Apellido', styles['Name']),
                   Paragraph(data.get('role',''), styles['HeaderSmall'])]], colWidths=[None, 6*cm])
    head.setStyle(TableStyle([
        ('BACKGROUND',(0,0),(-1,-1), colors.HexColor(accent)),
        ('LEFTPADDING',(0,0),(-1,-1),10),('RIGHTPADDING',(0,0),(-1,-1),10),
        ('TOPPADDING',(0,0),(-1,-1),8),('BOTTOMPADDING',(0,0),(-1,-1),8),
        ('TEXTCOLOR',(0,0),(-1,-1), colors.white),
    ]))
    story.append(head); story.append(Spacer(1,10))

    contact = [data.get(k,'').strip() for k in ('email','phone','city','website') if data.get(k,'').strip()]
    if contact: story.append(Paragraph(" • ".join(contact), styles['HeaderSmall']))
    story.append(Spacer(1,6))

    if data.get('summary'):
        story.append(Paragraph('Resumen', styles['Section']))
        story.append(Paragraph(data['summary'], styles['Body']))
        story.append(Spacer(1,6))

    sk = collect_skills(data)
    if sk:
        story.append(Paragraph('Habilidades', styles['Section']))
        story.append(Paragraph(" · ".join(sk), styles['Body']))
        story.append(Spacer(1,6))

    for title, company, dates, desc in collect_experiences(data):
        story.append(Paragraph(f"<b>{title}</b> — {company} <font color='#666666'>({dates})</font>", styles['Body']))
        for b in lines_to_bullets(desc): story.append(Paragraph(b, styles['ListItem'], bulletText='•'))
        story.append(Spacer(1,4))

    ed = collect_education(data)
    if ed: story.append(Paragraph('Formación', styles['Section']))
    for t_, s_, d_ in ed:
        story.append(Paragraph(f"<b>{t_}</b> — {s_} <font color='#666666'>({d_})</font>", styles['Body']))

    doc.build(story)
    pdf = buffer.getvalue(); buffer.close(); return pdf

# ====================== FORMULARIO (HTML+CSS+JS) ======================

FORM_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Generador de CV en PDF</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;background:#f6f9fc;margin:0;padding:0}
    .wrap{max-width:980px;margin:24px auto;padding:16px}
    .card{background:#fff;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,.08);padding:22px}
    h1{margin:0 0 8px}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .row-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
    label{font-weight:600;font-size:.9rem;color:#34495e}
    input,textarea,select{width:100%;padding:10px;border:1px solid #dfe6e9;border-radius:8px;font-size:14px}
    textarea{min-height:80px}
    .section{margin:16px 0}
    .btns{display:flex;gap:10px;margin-top:12px;flex-wrap:wrap}
    .btn{appearance:none;border:0;background:#0b7285;color:#fff;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}
    .btn.secondary{background:#e0e7ff;color:#1c3d5a}
    .btn.ghost{background:#eef2f7;color:#0b7285}
    .muted{color:#6b7280;font-size:.9rem}
    .small{font-size:.85rem;color:#6b7280}
    .hr{height:1px;background:#edf2f7;margin:16px 0}
    .group{border:1px dashed #e5e7eb;border-radius:10px;padding:12px;margin:8px 0}
    .topbar{display:flex;gap:10px;align-items:center;justify-content:space-between;margin-bottom:10px}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <div class="topbar">
        <h1>Generador de CV en PDF</h1>
        <div>
          <a class="btn secondary" href="/billing">Mejorar a Pro</a>
          <a class="btn ghost" href="?demo=1">Cargar ejemplo</a>
        </div>
      </div>
      <p class="muted">Rellena el formulario y obtén un PDF al instante.</p>
      <form method="post" action="{{ url_for('generate') }}" id="cvform">
        <div class="row">
          <div>
            <label>Plantilla</label>
            <select name="template">
              <option value="classic" {% if data.template == 'classic' %}selected{% endif %}>Clásica</option>
              <option value="twocol" {% if data.template == 'twocol' %}selected{% endif %}>Dos columnas</option>
              <option value="minimal" {% if data.template == 'minimal' %}selected{% endif %}>Minimal</option>
              <option value="modern" {% if data.template == 'modern' %}selected{% endif %}>Moderna</option>
            </select>
          </div>
          <div>
            <label>Foto (URL opcional)</label>
            <input name="photo_url" value="{{ data.photo_url }}" placeholder="https://...jpg">
          </div>
        </div>

        <div class="section">
          <label>Nombre completo</label>
          <input name="full_name" value="{{ data.full_name }}" required>
        </div>
        <div class="row">
          <div><label>Rol actual</label><input name="role" value="{{ data.role }}"></div>
          <div><label>Ciudad</label><input name="city" value="{{ data.city }}"></div>
        </div>
        <div class="row">
          <div><label>Email</label><input name="email" value="{{ data.email }}"></div>
          <div><label>Teléfono</label><input name="phone" value="{{ data.phone }}"></div>
        </div>
        <div class="section">
          <label>Web/LinkedIn</label>
          <input name="website" value="{{ data.website }}">
        </div>

        <div class="section">
          <label>Resumen (2–4 líneas)</label>
          <textarea name="summary">{{ data.summary }}</textarea>
        </div>

        <div class="section">
          <label>Habilidades</label>
          <div id="skillsContainer"></div>
          <div class="btns"><button type="button" class="btn ghost" onclick="addSkill()">+ Agregar habilidad</button></div>
          <p class="small">Añade una habilidad por fila.</p>
        </div>

        <div class="hr"></div>
        <h3>Experiencia</h3>
        <div id="expContainer"></div>
        <div class="btns"><button type="button" class="btn ghost" onclick="addExperience()">+ Agregar experiencia</button></div>

        <div class="hr"></div>
        <h3>Formación</h3>
        <div id="eduContainer"></div>
        <div class="btns"><button type="button" class="btn ghost" onclick="addEducation()">+ Agregar formación</button></div>

        <div class="btns" style="margin-top:18px">
          <button class="btn" type="submit">Generar PDF</button>
        </div>
        <p class="small">Privacidad: el PDF se genera al vuelo y no se guarda en servidor.</p>
      </form>
    </div>
  </div>

<script>
  function el(html){ const t=document.createElement('template'); t.innerHTML=html.trim(); return t.content.firstChild; }

  function addExperience(pref={}){
    const c=document.getElementById('expContainer');
    const g=el(`
      <div class="group">
        <div class="row-3">
          <div><label>Puesto</label><input name="exp_title" value="${pref.title||''}"></div>
          <div><label>Empresa</label><input name="exp_company" value="${pref.company||''}"></div>
          <div><label>Fechas</label><input name="exp_dates" value="${pref.dates||''}"></div>
        </div>
        <div class="section">
          <label>Logros/Tareas (una por línea o separadas por ';')</label>
          <textarea name="exp_desc">${pref.desc||''}</textarea>
        </div>
        <div class="btns"><button type="button" class="btn secondary" onclick="this.closest('.group').remove()">Eliminar</button></div>
      </div>`);
    c.appendChild(g);
  }

  function addEducation(pref={}){
    const c=document.getElementById('eduContainer');
    const g=el(`
      <div class="group">
        <div class="row-3">
          <div><label>Título</label><input name="edu_title" value="${pref.title||''}"></div>
          <div><label>Centro</label><input name="edu_school" value="${pref.school||''}"></div>
          <div><label>Fechas</label><input name="edu_dates" value="${pref.dates||''}"></div>
        </div>
        <div class="btns"><button type="button" class="btn secondary" onclick="this.closest('.group').remove()">Eliminar</button></div>
      </div>`);
    c.appendChild(g);
  }

  function addSkill(value=''){
    const c=document.getElementById('skillsContainer');
    const g=el(`<div class="group"><div class="row"><div><input name="skill" value="${value}" placeholder="p.ej. Python"></div><div><button type="button" class="btn secondary" onclick="this.closest('.group').remove()">Eliminar</button></div></div></div>`);
    c.appendChild(g);
  }

  (function preload(){
    const exp = {{ data.exp_title|tojson if data.exp_title else '[]' }};
    const comp = {{ data.exp_company|tojson if data.exp_company else '[]' }};
    const dates = {{ data.exp_dates|tojson if data.exp_dates else '[]' }};
    const desc = {{ data.exp_desc|tojson if data.exp_desc else '[]' }};
    for(let i=0;i<Math.max(exp.length,comp.length,dates.length,desc.length);i++){
      addExperience({title:exp[i]||'', company:comp[i]||'', dates:dates[i]||'', desc:desc[i]||''});
    }
    const et = {{ data.edu_title|tojson if data.edu_title else '[]' }};
    const es = {{ data.edu_school|tojson if data.edu_school else '[]' }};
    const ed = {{ data.edu_dates|tojson if data.edu_dates else '[]' }};
    for(let i=0;i<Math.max(et.length,es.length,ed.length);i++){
      addEducation({title:et[i]||'', school:es[i]||'', dates:ed[i]||''});
    }
    const skills = {{ (data.skills.split(',') if data.skills else [])|tojson }};
    if(skills.length){ skills.forEach(s=>addSkill(s.trim())); } else { addSkill(''); }
    if(document.getElementById('expContainer').children.length===0){ addExperience({}); }
    if(document.getElementById('eduContainer').children.length===0){ addEducation({}); }
  })();
</script>
</body>
</html>
"""

# ====================== RUTAS PRINCIPALES ======================

@app.get("/")
def index():
    demo = request.args.get("demo")
    data = default_data() if demo else empty_data()
    return render_template_string(FORM_HTML, data=data)

@app.post("/generate")
def generate():
    simple_fields = ['template','photo_url','full_name','role','city','email','phone','website','summary','skills']
    data = {k: request.form.get(k, '') for k in simple_fields}

    tpl = (data.get('template') or 'classic').strip().lower()
    if tpl == 'twocol':       pdf = build_pdf_twocol(data)
    elif tpl == 'minimal':    pdf = build_pdf_minimal(data)
    elif tpl == 'modern':     pdf = build_pdf_modern(data)
    else:                     pdf = build_pdf_classic(data)

    filename = f"CV_{(data.get('full_name') or 'anonimo').replace(' ', '_')}.pdf"
    resp = make_response(pdf)
    resp.headers['Content-Type'] = 'application/pdf'
    resp.headers['Content-Disposition'] = f'attachment; filename="{filename}"'
    return resp

# ====================== STRIPE: BILLING + WEBHOOK ======================

@app.get("/billing")
def billing_page():
    # Página de prueba simple para Checkout
    monthly_ok = bool(PRICE_MONTHLY)
    yearly_ok  = bool(PRICE_YEARLY)
    note = "" if (monthly_ok or yearly_ok) else "<p style='color:#b91c1c'>Configura STRIPE_PRICE_PRO_MONTHLY / YEARLY en Render.</p>"
    html = f"""
    <!doctype html><html><head><meta charset="utf-8"><title>Mejorar a Pro</title></head>
    <body style="font-family:system-ui;padding:20px;max-width:720px;margin:auto">
      <h2>Mejorar a Pro</h2>
      <p>Suscripción segura con Stripe (modo test).</p>
      {note}
      <form method="post" action="/create-checkout-session" style="max-width:420px">
        <label>Email (recibirá el recibo):</label><br>
        <input name="email" placeholder="tu@email.com" style="width:100%;padding:8px"><br><br>
        <label>Plan:</label><br>
        <select name="price">
          {"<option value='monthly'>Pro mensual</option>" if monthly_ok else ""}
          {"<option value='yearly'>Pro anual</option>" if yearly_ok else ""}
        </select><br><br>
        <button type="submit" style="padding:10px 14px;font-weight:bold">Pagar</button>
      </form>
      <p style="margin-top:16px"><a href="/">Volver a la app</a></p>
    </body></html>
    """
    return html

@app.post("/create-checkout-session")
def create_checkout_session():
    email = request.form.get("email", "").strip()
    plan = request.form.get("price", "monthly").strip().lower()
    price_id = PRICE_MONTHLY if plan == "monthly" else PRICE_YEARLY
    if not stripe.api_key or not price_id:
        return jsonify({"error": "Stripe no está configurado (SECRET_KEY o PRICE_ID)"}), 400

    try:
        session = stripe.checkout.Session.create(
            mode="subscription",
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            customer_email=email if email else None,
            success_url="https://app.aignitionagency.com/success?session_id={CHECKOUT_SESSION_ID}",
            cancel_url="https://app.aignitionagency.com/cancel"
        )
        return redirect(session.url, code=303)
    except Exception as e:
        return jsonify({"error": str(e)}), 400

@app.get("/success")
def success():
    return """
    <!doctype html><html><head><meta charset="utf-8"><title>¡Éxito!</title></head>
    <body style="font-family:system-ui;padding:20px">
      <h2>¡Pago completado!</h2>
      <p>Tu suscripción Pro está activa (modo test). Revisa tu email.</p>
      <p><a href="/">Volver a la app</a></p>
    </body></html>
    """

@app.get("/cancel")
def cancel():
    return """
    <!doctype html><html><head><meta charset="utf-8"><title>Cancelado</title></head>
    <body style="font-family:system-ui;padding:20px">
      <h2>Pago cancelado</h2>
      <p>No se ha realizado ningún cargo.</p>
      <p><a href="/">Volver a la app</a></p>
    </body></html>
    """

@app.post("/webhooks/stripe")
def stripe_webhook():
    # Nota: en esta versión no persistimos usuario/plan (no hay BD aún).
    # Este endpoint valida el evento y sirve de base para cuando añadamos Postgres.
    payload = request.data
    sig_header = request.headers.get("Stripe-Signature", "")
    try:
        if WEBHOOK_SECRET:
            event = stripe.Webhook.construct_event(payload, sig_header, WEBHOOK_SECRET)
        else:
            # Permite probar sin configurar whsec (NO recomendado en producción)
            event = stripe.Event.construct_from(request.get_json(force=True), stripe.api_key)
    except Exception as e:
        return {"error": str(e)}, 400

    etype = event.get("type")
    # data = event.get("data", {}).get("object", {})  # <- cuando añadamos BD, usaremos estos datos

    # Aquí solo confirmamos recepción
    if etype in ("checkout.session.completed",
                 "customer.subscription.updated",
                 "customer.subscription.deleted"):
        pass

    return {"received": True}, 200

# ====================== HEALTH ======================

@app.get("/health")
def health():
    return {"ok": True}

# ====================== DATOS POR DEFECTO ======================

def empty_data():
    return {
        'template': 'classic',
        'photo_url': '',
        'full_name': '', 'role': '', 'city': '', 'email': '', 'phone': '', 'website': '',
        'summary': '', 'skills': '',
        'exp_title': [], 'exp_company': [], 'exp_dates': [], 'exp_desc': [],
        'edu_title': [], 'edu_school': [], 'edu_dates': [],
    }

def default_data():
    return {
        'template': 'modern',
        'photo_url': 'https://picsum.photos/300',
        'full_name': 'Alexis Galán',
        'role': 'Data Analyst / Python Developer',
        'city': 'Madrid, España',
        'email': 'alexis@example.com',
        'phone': '+34 600 123 456',
        'website': 'https://linkedin.com/in/alexisgalan',
        'summary': ('Analista de datos con 5+ años construyendo ETLs, dashboards y automatizaciones. '
                    'Me gusta convertir datos en decisiones y crear herramientas simples que la gente usa.'),
        'skills': 'Python, SQL, Airflow, FastAPI, Pandas, Power BI, Git, Docker, Linux, Scraping',
        'exp_title': ['Data Analyst','Python Developer (Freelance)'],
        'exp_company': ['Iberia','Proyectos varios'],
        'exp_dates': ['2022 – Actualidad','2020 – 2022'],
        'exp_desc': [
            'Automatización de reportes en Power BI; Optimización de consultas SQL; Ahorro del 18% en tiempo de preparación de datos',
            'Scrapers para monitorizar precios; APIs con FastAPI; Integración con Stripe para un SaaS pequeño',
        ],
        'edu_title': ['Grado en Estadística'],
        'edu_school': ['UCM'],
        'edu_dates': ['2016 – 2020'],
    }

# ====================== MAIN ======================

if __name__ == '__main__':
    # Requisitos:
    # pip install -r requirements.txt
    # Variables en entorno (Render):
    #  - STRIPE_SECRET_KEY
    #  - STRIPE_PRICE_PRO_MONTHLY
    #  - STRIPE_PRICE_PRO_YEARLY
    #  - STRIPE_WEBHOOK_SECRET (después de crear webhook)
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)), debug=True)
