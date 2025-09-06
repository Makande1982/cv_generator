# cv_generator.py
# -------------------------------------------------------------
# App Flask que muestra un formulario y genera un CV en PDF.
# 100% Python puro usando ReportLab (sin dependencias del sistema).
# -------------------------------------------------------------
from flask import Flask, request, make_response, render_template_string, redirect, url_for
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib import colors
from reportlab.lib.units import cm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from io import BytesIO
from datetime import datetime

app = Flask(__name__)

# ---------------------- Utils ----------------------

def build_pdf(data: dict) -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=2*cm, rightMargin=2*cm, topMargin=2*cm, bottomMargin=2*cm)

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(name="Name", fontSize=20, leading=24, spaceAfter=6, textColor=colors.HexColor('#222222')))
    styles.add(ParagraphStyle(name="Header", fontSize=11, leading=14, textColor=colors.HexColor('#666666')))
    styles.add(ParagraphStyle(name="Section", fontSize=14, leading=18, spaceBefore=10, spaceAfter=6, textColor=colors.HexColor('#0b7285')))
    styles.add(ParagraphStyle(name="Body", fontSize=10, leading=14))
    styles.add(ParagraphStyle(name="Bullet", fontSize=10, leading=14, leftIndent=12, bulletIndent=0))

    story = []

    # Header: Name and contact
    full_name = data.get('full_name', '').strip() or 'Nombre Apellido'
    role = data.get('role', '').strip()
    contact = []
    email = data.get('email', '').strip()
    phone = data.get('phone', '').strip()
    city = data.get('city', '').strip()
    website = data.get('website', '').strip()
    if email: contact.append(email)
    if phone: contact.append(phone)
    if city: contact.append(city)
    if website: contact.append(website)

    story.append(Paragraph(full_name, styles['Name']))
    if role:
        story.append(Paragraph(role, styles['Header']))
    if contact:
        story.append(Paragraph(" • ".join(contact), styles['Header']))
    story.append(Spacer(1, 10))

    # Summary
    summary = data.get('summary', '').strip()
    if summary:
        story.append(Paragraph('Resumen', styles['Section']))
        story.append(Paragraph(summary, styles['Body']))
        story.append(Spacer(1, 6))

    # Skills (comma separated)
    skills = [s.strip() for s in (data.get('skills', '') or '').split(',') if s.strip()]
    if skills:
        story.append(Paragraph('Habilidades', styles['Section']))
        # Make a simple 2-3 column table based on count
        cols = 3 if len(skills) >= 9 else (2 if len(skills) >= 6 else 1)
        rows = []
        for i in range(0, len(skills), cols):
            row = skills[i:i+cols]
            while len(row) < cols:
                row.append('')
            rows.append(row)
        t = Table(rows, hAlign='LEFT')
        t.setStyle(TableStyle([
            ('FONTNAME', (0,0), (-1,-1), 'Helvetica'),
            ('FONTSIZE', (0,0), (-1,-1), 9),
            ('TEXTCOLOR', (0,0), (-1,-1), colors.HexColor('#333333')),
            ('BOTTOMPADDING', (0,0), (-1,-1), 4),
        ]))
        story.append(t)
        story.append(Spacer(1, 6))

    # Experience: expects multiple entries
    exp_titles = request.form.getlist('exp_title') or data.get('exp_title', [])
    exp_company = request.form.getlist('exp_company') or data.get('exp_company', [])
    exp_dates = request.form.getlist('exp_dates') or data.get('exp_dates', [])
    exp_desc = request.form.getlist('exp_desc') or data.get('exp_desc', [])
    experiences = []
    for i in range(max(len(exp_titles), len(exp_company), len(exp_dates), len(exp_desc))):
        title = (exp_titles[i] if i < len(exp_titles) else '').strip()
        company = (exp_company[i] if i < len(exp_company) else '').strip()
        dates = (exp_dates[i] if i < len(exp_dates) else '').strip()
        desc = (exp_desc[i] if i < len(exp_desc) else '').strip()
        if any([title, company, dates, desc]):
            experiences.append((title, company, dates, desc))

    if experiences:
        story.append(Paragraph('Experiencia', styles['Section']))
        for (title, company, dates, desc) in experiences:
            header = f"<b>{title or 'Puesto'}</b> — {company or ''} <font color='#666666'>({dates or ''})</font>"
            story.append(Paragraph(header, styles['Body']))
            if desc:
                # bullet lines by splitting \n or ';'
                bullets = [b.strip() for b in desc.replace(';', '\n').split('\n') if b.strip()]
                for b in bullets:
                    story.append(Paragraph(b, styles['Bullet'], bulletText='•'))
            story.append(Spacer(1, 4))

    # Education
    edu_entries = [
        (
            ((request.form.getlist('edu_title') or data.get('edu_title', []))[i] if i < len(request.form.getlist('edu_title') or data.get('edu_title', [])) else ''),
            ((request.form.getlist('edu_school') or data.get('edu_school', []))[i] if i < len(request.form.getlist('edu_school') or data.get('edu_school', [])) else ''),
            ((request.form.getlist('edu_dates') or data.get('edu_dates', []))[i] if i < len(request.form.getlist('edu_dates') or data.get('edu_dates', [])) else ''),
        )
        for i in range(max(len(request.form.getlist('edu_title') or data.get('edu_title', [])), len(request.form.getlist('edu_school') or data.get('edu_school', [])), len(request.form.getlist('edu_dates') or data.get('edu_dates', []))))
    ]
    edu_entries = [e for e in edu_entries if any(e)]

    if edu_entries:
        story.append(Paragraph('Formación', styles['Section']))
        for (title, school, dates) in edu_entries:
            header = f"<b>{title or 'Título'}</b> — {school or ''} <font color='#666666'>({dates or ''})</font>"
            story.append(Paragraph(header, styles['Body']))
        story.append(Spacer(1, 4))

    # Footer
    generated = datetime.now().strftime('%Y-%m-%d')
    story.append(Spacer(1, 8))
    story.append(Paragraph(f"<font size=8 color='#888888'>Generado con cv_generator.py · {generated}</font>", styles['Body']))

    doc.build(story)
    pdf = buffer.getvalue()
    buffer.close()
    return pdf

# ---------------------- HTML Form ----------------------

FORM_HTML = """
<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>Generador de CV en PDF</title>
  <style>
    body{font-family:system-ui,-apple-system,Segoe UI,Roboto,Ubuntu,Helvetica,Arial,sans-serif;background:#f6f9fc;margin:0;padding:0}
    .wrap{max-width:980px;margin:24px auto;padding:16px}
    .card{background:#fff;border-radius:12px;box-shadow:0 4px 14px rgba(0,0,0,.08);padding:22px}
    h1{margin:0 0 8px}
    .row{display:grid;grid-template-columns:1fr 1fr;gap:12px}
    .row-3{display:grid;grid-template-columns:1fr 1fr 1fr;gap:12px}
    label{font-weight:600;font-size:.9rem;color:#34495e}
    input,textarea{width:100%;padding:10px;border:1px solid #dfe6e9;border-radius:8px;font-size:14px}
    textarea{min-height:80px}
    .section{margin:16px 0}
    .btns{display:flex;gap:10px;margin-top:12px}
    .btn{appearance:none;border:0;background:#0b7285;color:#fff;border-radius:10px;padding:10px 14px;font-weight:700;cursor:pointer}
    .btn.secondary{background:#e0e7ff;color:#1c3d5a}
    .muted{color:#6b7280;font-size:.9rem}
    .small{font-size:.85rem;color:#6b7280}
    .hr{height:1px;background:#edf2f7;margin:16px 0}
  </style>
</head>
<body>
  <div class="wrap">
    <div class="card">
      <h1>Generador de CV en PDF</h1>
      <p class="muted">Rellena el formulario y obtén un PDF al instante. <a href="?demo=1">Rellenar con ejemplo</a></p>
      <form method="post" action="{{ url_for('generate') }}">
        <div class="section">
          <label>Nombre completo</label>
          <input name="full_name" value="{{ data.full_name }}" required>
        </div>
        <div class="row">
          <div>
            <label>Rol actual</label>
            <input name="role" value="{{ data.role }}">
          </div>
          <div>
            <label>Ciudad</label>
            <input name="city" value="{{ data.city }}">
          </div>
        </div>
        <div class="row">
          <div>
            <label>Email</label>
            <input name="email" value="{{ data.email }}">
          </div>
          <div>
            <label>Teléfono</label>
            <input name="phone" value="{{ data.phone }}">
          </div>
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
          <label>Habilidades (separadas por comas)</label>
          <input name="skills" value="{{ data.skills }}">
        </div>

        <div class="hr"></div>
        <h3>Experiencia</h3>
        {% for i in range(3) %}
        <div class="row-3">
          <div>
            <label>Puesto</label>
            <input name="exp_title" value="{{ (data.exp_title[i] if data.exp_title and i < data.exp_title|length else '') }}">
          </div>
          <div>
            <label>Empresa</label>
            <input name="exp_company" value="{{ (data.exp_company[i] if data.exp_company and i < data.exp_company|length else '') }}">
          </div>
          <div>
            <label>Fechas (p.ej. 2022–2024)</label>
            <input name="exp_dates" value="{{ (data.exp_dates[i] if data.exp_dates and i < data.exp_dates|length else '') }}">
          </div>
        </div>
        <div class="section">
          <label>Logros/Tareas (una por línea o separadas por ';')</label>
          <textarea name="exp_desc">{{ (data.exp_desc[i] if data.exp_desc and i < data.exp_desc|length else '') }}</textarea>
        </div>
        {% endfor %}

        <div class="hr"></div>
        <h3>Formación</h3>
        {% for i in range(2) %}
        <div class="row-3">
          <div>
            <label>Título</label>
            <input name="edu_title" value="{{ (data.edu_title[i] if data.edu_title and i < data.edu_title|length else '') }}">
          </div>
          <div>
            <label>Centro</label>
            <input name="edu_school" value="{{ (data.edu_school[i] if data.edu_school and i < data.edu_school|length else '') }}">
          </div>
          <div>
            <label>Fechas</label>
            <input name="edu_dates" value="{{ (data.edu_dates[i] if data.edu_dates and i < data.edu_dates|length else '') }}">
          </div>
        </div>
        {% endfor %}

        <div class="btns">
          <button class="btn" type="submit">Generar PDF</button>
          <a class="btn secondary" href="?demo=1">Cargar ejemplo</a>
        </div>
        <p class="small">Privacidad: el PDF se genera al vuelo y no guardamos nada en servidor (ejemplo local).</p>
      </form>
    </div>
  </div>
</body>
</html>
"""

# ---------------------- Routes ----------------------

@app.get('/')
def index():
    demo = request.args.get('demo')
    data = default_data() if demo else empty_data()
    return render_template_string(FORM_HTML, data=data)

@app.post('/generate')
def generate():
    # Construir dict con lo enviado para también reusar en PDF
    data = {k: request.form.get(k, '') for k in ['full_name','role','city','email','phone','website','summary','skills']}
    # Campos repetibles: Flask los entrega con getlist en build_pdf
    pdf_bytes = build_pdf(data)

    filename = f"CV_{(data.get('full_name') or 'anonimo').replace(' ', '_')}.pdf"
    response = make_response(pdf_bytes)
    response.headers.set('Content-Type', 'application/pdf')
    response.headers.set('Content-Disposition', 'attachment', filename=filename)
    return response

# ---------------------- Defaults ----------------------

def empty_data():
    return {
        'full_name': '', 'role': '', 'city': '', 'email': '', 'phone': '', 'website': '',
        'summary': '', 'skills': '',
        'exp_title': ['','',''], 'exp_company': ['','',''], 'exp_dates': ['','',''], 'exp_desc': ['','',''],
        'edu_title': ['',''], 'edu_school': ['',''], 'edu_dates': ['',''],
    }


def default_data():
    return {
        'full_name': 'Alexis Galán',
        'role': 'Data Analyst / Python Developer',
        'city': 'Madrid, España',
        'email': 'alexis@example.com',
        'phone': '+34 600 123 456',
        'website': 'linkedin.com/in/alexisgalan',
        'summary': (
            'Analista de datos con 5+ años construyendo ETLs, dashboards y automatizaciones. '
            'Me gusta convertir datos en decisiones de negocio y crear herramientas simples que la gente usa.'
        ),
        'skills': 'Python, SQL, Airflow, FastAPI, Pandas, Power BI, Git, Docker, Linux, Scraping',
        'exp_title': [
            'Data Analyst',
            'Python Developer (Freelance)',
            'Intern Datos',
        ],
        'exp_company': [
            'Iberia',
            'Proyectos varios',
            'Universidad Complutense',
        ],
        'exp_dates': [
            '2022 – Actualidad',
            '2020 – 2022',
            '2019 – 2020',
        ],
        'exp_desc': [
            'Automatización de reportes en Power BI; Optimización de consultas SQL; Ahorro de 18% en tiempo de preparación de datos',
            'Scrapers para monitorizar precios; APIs con FastAPI; Integración con Stripe para un SaaS pequeño',
            'Soporte en limpieza y visualización de datos; Documentación y QA',
        ],
        'edu_title': [
            'Grado en Estadística',
            'Curso de Especialización en Ciencia de Datos',
        ],
        'edu_school': [
            'UCM',
            'Datacamp / Coursera',
        ],
        'edu_dates': [
            '2016 – 2020',
            '2021',
        ],
    }

# ---------------------- Main ----------------------

if __name__ == '__main__':
    # Para desarrollo local: python cv_generator.py
    # Navega a http://127.0.0.1:5000 y usa "Rellenar con ejemplo"
    app.run(debug=True)
