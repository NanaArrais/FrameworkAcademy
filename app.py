"""Framework Academy: Flask + PostgreSQL, painel do professor e atividades."""
import os
import re
import csv
import io
import secrets
import json
from pathlib import Path
from datetime import datetime, timezone
from difflib import SequenceMatcher
from functools import wraps
from html.parser import HTMLParser
from flask import Flask, render_template, request, jsonify, session, Response
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import UniqueConstraint, func
from werkzeug.security import check_password_hash

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.getenv('SECRET_KEY', secrets.token_hex(32)),
    SQLALCHEMY_DATABASE_URI=os.getenv('DATABASE_URL', 'postgresql+psycopg://localhost:5432/framework_academy').replace('postgres://', 'postgresql+psycopg://', 1),
    SQLALCHEMY_TRACK_MODIFICATIONS=False,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE='Lax',
    SESSION_COOKIE_SECURE=os.getenv('COOKIE_SECURE', 'false').lower() == 'true',
    MAX_CONTENT_LENGTH=300_000,
)
db = SQLAlchemy(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    enrollment = db.Column(db.String(48), unique=True, nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    course = db.Column(db.String(120), nullable=False)
    created_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    submissions = db.relationship('Submission', back_populates='student', cascade='all, delete-orphan')

class Submission(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    framework = db.Column(db.String(20), nullable=False)
    exercise = db.Column(db.Integer, nullable=False)
    variant = db.Column(db.String(12), default='top', nullable=False)
    code = db.Column(db.Text, nullable=False)
    passed = db.Column(db.Boolean, default=False, nullable=False)
    score = db.Column(db.Integer, default=0, nullable=False)
    feedback = db.Column(db.Text, nullable=False, default='')
    submitted_at = db.Column(db.DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
    student = db.relationship('Student', back_populates='submissions')

class Award(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    framework = db.Column(db.String(20), nullable=False)
    exercise = db.Column(db.Integer, nullable=False)
    __table_args__ = (UniqueConstraint('student_id', 'framework', 'exercise', name='uq_student_exercise'),)

class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags=[]; self.classes=[]; self.links=[]; self.attrs=[]; self.texts=[]
        self._link=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs); self.tags.append(tag); self.attrs.append((tag,a)); self.classes.extend(a.get('class','').split());
        if tag=='a': self._link=True
    def handle_endtag(self, tag):
        if tag=='a': self._link=False
    def handle_data(self, data):
        self.texts.append(data)
        if self._link: self.links.append(data)

REFERENCES=json.loads((Path(__file__).parent/'reference_samples.json').read_text(encoding='utf-8'))

def normalized_html(code):
    """Normalize whitespace/comments to catch exact copied sample markup."""
    parser=Inspector()
    parser.feed(code)
    body=re.search(r'<body[^>]*>(.*?)</body>',code,re.I|re.S)
    material=body.group(1) if body else code
    material=re.sub(r'<!--[\s\S]*?-->','',material)
    return re.sub(r'\s+',' ',material).strip().casefold()

def check_submission(source, fw, exercise, variant):
    doc=Inspector()
    try: doc.feed(source)
    except Exception: return False,['HTML não pôde ser analisado.']
    sample=(REFERENCES['navSamples'][fw][variant] if exercise==0 else REFERENCES['lessonCodeExamples'][fw][exercise])
    clean_sample=normalized_html(sample)
    clean_user=normalized_html(source)
    if clean_sample==clean_user or (len(clean_sample)>60 and clean_sample in clean_user):
        return False,['Não é permitido enviar uma cópia integral do código de referência.']
    tags=doc.tags; classes=set(doc.classes); a=doc.attrs
    text=' '.join(doc.texts).lower()
    has=lambda tag:tag in tags
    regex=lambda pattern:bool(re.search(pattern, ' '.join(doc.classes), re.I))
    criteria=[]
    if exercise==0:
        criteria=[(has('nav') or has('header'),'Incluir <nav> ou <header>'),
                  (any(x for x in a if x[0]=='a' and x[1].get('href')) and len(text.strip())>5,'Adicionar marca com link')]
        if variant=='side':
            criteria += [(any('sidenav' in c or 'offcanvas' in c for c in classes) or has('aside'),'Criar painel lateral'),
                         (any('data-target' in x[1] or 'data-bs-target' in x[1] or 'aria-controls' in x[1] for x in a),'Associar botão ao menu lateral')]
    elif exercise==1:
        criteria=[(has('section'),'Criar seção'),(any(t in tags for t in ['h1','h2','h3','h4']),'Adicionar título'),(regex(r'\b(bg-|red|pink|purple|deep-purple|indigo|blue|teal|green|amber|orange|grey|cyan|brown)'),'Aplicar classe de cor')]
    elif exercise==2:
        criteria=[(regex(r'\b(grid|row)\b'),'Criar grid'),(len([t for t in tags if t in ['article']])+len([v for t,v in a if t=='div' and any('card' in c for c in v.get('class','').split())])>=3 or len([v for t,v in a if t=='div' and re.search(r'\bcol(?:-|\s)',v.get('class',''))])>=3,'Incluir três cards/colunas'),(regex(r'\b(md:|sm:|col-md-|\bm\d+)'),'Aplicar responsividade')]
    elif exercise==3:
        criteria=[(has('button'),'Criar botão'),(regex(r'\bbtn\b|\bbg-[\w-]+\b'),'Aplicar classe de botão/cor'),(any(len(re.sub(r'<[^>]+>', '', button).strip()) > 2 for button in re.findall(r'<button\b[^>]*>(.*?)</button\s*>', source, re.I | re.S)),'Adicionar texto de ação')]
    elif exercise==4:
        criteria=[(regex(r'\bcard\b|\bshadow\b'),'Criar card'),(any(t in tags for t in ['h2','h3','h4','h5']),'Adicionar título'),(has('p'),'Adicionar descrição')]
    elif exercise==5:
        criteria=[(has('form'),'Criar formulário'),(sum(t=='input' for t in tags)>=2,'Incluir dois campos'),(any(t=='button' and d.get('type')=='submit' for t,d in a),'Adicionar envio')]
    elif exercise==6:
        criteria=[(any(t in tags for t in ['h1','h2','h3']),'Adicionar título'),(has('p'),'Adicionar parágrafo'),(regex(r'flow-text|text-|fs-|fw-|font-'),'Estilizar tipografia')]
    elif exercise==7:
        criteria=[(has('section'),'Criar seção'),(any(t in tags for t in ['h1','h2','h3','h4']),'Adicionar título'),(regex(r'\b(p-|m-|py-|px-|my-|mx-|section|container)'),'Aplicar espaçamento')]
    elif exercise==8:
        criteria=[(has('img'),'Inserir imagem'),(any(t=='img' and d.get('alt','').strip() for t,d in a),'Adicionar texto alternativo'),(regex(r'img-fluid|responsive-img|w-full|max-w-full'),'Tornar imagem responsiva')]
    elif exercise==9:
        criteria=[(has('ul') or has('ol'),'Criar lista'),(tags.count('li')>=3,'Adicionar 3 itens'),(regex(r'collection|list-group|divide-|border'),'Estilizar lista')]
    elif exercise==10:
        criteria=[(has('p') or has('div'),'Criar mensagem'),(len(text.strip())>=12,'Adicionar texto'),(regex(r'alert|card-panel|bg-|border'),'Aplicar destaque')]
    elif exercise==11:
        criteria=[(has('table'),'Criar tabela'),(has('thead') and has('th'),'Adicionar cabeçalho'),(tags.count('tr')>=3,'Adicionar duas linhas'),(regex(r'table|striped|highlight|border'),'Estilizar tabela')]
    elif exercise==12:
        criteria=[(any(t in tags for t in ['h1','h2','h3']),'Adicionar título'),(regex(r'text-center|center-align|justify-center'),'Alinhar conteúdo'),(tags.count('span')>=2 or tags.count('div')>=2,'Criar dois elementos')]
    else:
        criteria=[(has('footer'),'Criar rodapé'),('©' in source or 'copyright' in text,'Adicionar copyright'),(has('a'),'Incluir link'),(regex(r'page-footer|bg-|p-|text-'),'Aplicar estilo')]
    misses=[label for ok,label in criteria if not ok]
    # Comparison against commented examples is also performed in the client UI.
    if len(re.sub(r'\s+','',source))<100: misses.append('Código incompleto')
    return not misses, misses

def student_only(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not session.get('student_id'): return jsonify(error='Identifique-se antes de enviar.'),401
        return fn(*args, **kwargs)
    return decorated

def teacher_only(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not session.get('teacher'):return jsonify(error='Acesso restrito ao professor.'),403
        return fn(*args, **kwargs)
    return decorated

@app.get('/')
def home(): return render_template('index.html')

@app.post('/api/student/register')
def register():
    data=request.get_json(silent=True) or {}
    name=str(data.get('name','')).strip(); enrollment=str(data.get('enrollment','')).strip(); course=str(data.get('course','')).strip()
    if not 3<=len(name)<=120 or not re.fullmatch(r'[\w.-]{3,48}',enrollment) or not 2<=len(course)<=120:
        return jsonify(error='Preencha nome, matrícula (3–48 caracteres) e curso.'),400
    student=Student.query.filter_by(enrollment=enrollment).first()
    if student:
        if student.name.casefold()!=name.casefold() or student.course.casefold()!=course.casefold():
            return jsonify(error='Matrícula já cadastrada com outros dados. Procure o professor.'),409
    else:
        student=Student(name=name,enrollment=enrollment,course=course);db.session.add(student);db.session.commit()
    session['student_id']=student.id
    return jsonify(student={'name':student.name,'enrollment':student.enrollment,'course':student.course}, progress=progress_of(student.id))

def progress_of(student_id):
    awards=Award.query.filter_by(student_id=student_id).all()
    return {'points':100*len(awards),'completed':[{'framework':a.framework,'exercise':a.exercise} for a in awards]}

@app.get('/api/student/me')
@student_only
def me():
    student=db.session.get(Student,session['student_id'])
    if not student:return jsonify(error='Aluno não encontrado.'),404
    return jsonify(student={'name':student.name,'enrollment':student.enrollment,'course':student.course},progress=progress_of(student.id))

@app.post('/api/submissions')
@student_only
def submit():
    data=request.get_json(silent=True) or {}
    code=data.get('code',''); fw=data.get('framework'); ex=data.get('exercise'); variant=data.get('variant','top')
    if not isinstance(code,str) or len(code)>100_000 or fw not in ('bootstrap','tailwind','materialize') or type(ex)!=int or not 0<=ex<14 or variant not in ('top','side'):
        return jsonify(error='Dados do exercício inválidos.'),400
    if ex>0 and not Award.query.filter_by(student_id=session['student_id'],framework=fw,exercise=ex-1).first():
        return jsonify(error='Conclua o exercício anterior antes de avançar.'),403
    passed,missing=check_submission(code,fw,ex,variant)
    feedback='Concluído' if passed else 'Pendências: '+', '.join(missing)
    obj=Submission(student_id=session['student_id'],framework=fw,exercise=ex,variant=variant,code=code,passed=passed,score=100 if passed else 0,feedback=feedback)
    db.session.add(obj)
    if passed and not Award.query.filter_by(student_id=session['student_id'],framework=fw,exercise=ex).first():
        db.session.add(Award(student_id=session['student_id'],framework=fw,exercise=ex))
    db.session.commit()
    return jsonify(passed=passed,missing=missing,progress=progress_of(session['student_id']))

@app.post('/api/teacher/login')
def teacher_login():
    password=(request.get_json(silent=True) or {}).get('password','')
    configured=os.getenv('TEACHER_PASSWORD_HASH')
    if not configured:return jsonify(error='Configure TEACHER_PASSWORD_HASH no servidor.'),503
    if not isinstance(password,str) or not check_password_hash(configured,password):return jsonify(error='Senha incorreta.'),401
    session['teacher']=True
    return jsonify(ok=True)

@app.post('/api/teacher/logout')
def teacher_logout():session.pop('teacher',None);return jsonify(ok=True)

@app.get('/api/teacher/results')
@teacher_only
def results():
    students=Student.query.order_by(Student.course,Student.name).all()
    data=[]
    for s in students:
        attempts=Submission.query.filter_by(student_id=s.id).order_by(Submission.submitted_at.desc()).all()
        data.append({'id':s.id,'name':s.name,'enrollment':s.enrollment,'course':s.course,'points':progress_of(s.id)['points'],
                     'completed':progress_of(s.id)['completed'],'attempts':len(attempts),'last_attempt':attempts[0].submitted_at.isoformat() if attempts else None})
    return jsonify(students=data)

@app.get('/api/teacher/student/<int:student_id>')
@teacher_only
def student_attempts(student_id):
    s=db.session.get(Student,student_id)
    if not s:return jsonify(error='Aluno não encontrado.'),404
    rows=Submission.query.filter_by(student_id=student_id).order_by(Submission.submitted_at.desc()).limit(200).all()
    return jsonify(name=s.name,attempts=[{'framework':x.framework,'exercise':x.exercise+1,'variant':x.variant,'passed':x.passed,'feedback':x.feedback,'code':x.code,'at':x.submitted_at.isoformat()} for x in rows])

@app.get('/api/teacher/export.csv')
@teacher_only
def export_csv():
    out=io.StringIO();w=csv.writer(out);w.writerow(['Nome','Matrícula','Curso','Pontuação','Atividades concluídas'])
    for s in Student.query.order_by(Student.name):
        p=progress_of(s.id);w.writerow([s.name,s.enrollment,s.course,p['points'],len(p['completed'])])
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="resultados_framework_academy.csv"'})

if __name__=='__main__':
    with app.app_context():db.create_all()
    app.run(port=int(os.getenv('PORT','5000')),debug=os.getenv('FLASK_DEBUG')=='1')
