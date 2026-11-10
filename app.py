"""Framework Academy: Flask + PostgreSQL, painel do professor e atividades."""
import os
import re
import csv
import io
import secrets
import json
from pathlib import Path
from datetime import datetime, timezone, date, time, timedelta
from zoneinfo import ZoneInfo
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

class PracticeRun(db.Model):
    """Uma rodada de prática por identificação; tabela nova, sem alterar as existentes."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    started_at = db.Column(db.DateTime(timezone=True), nullable=False, index=True)
    last_approved_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    ended_at = db.Column(db.DateTime(timezone=True), nullable=True)

class StudentAccess(db.Model):
    """Registro de abertura do laboratório. Horários UTC; a interface converte para Fortaleza."""
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False, index=True)
    accessed_at = db.Column(db.DateTime(timezone=True), nullable=False,
                            default=lambda: datetime.now(timezone.utc), index=True)

def register_student_access(student_id):
    db.session.add(StudentAccess(student_id=student_id))
    db.session.commit()

def iso_utc(value):
    """Devolve um timestamp ISO com fuso, inclusive em bancos que retornam datetime ingênuo."""
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()

def ensure_practice_run(student_id):
    """Recupera a rodada da sessão ou cria uma para sessões anteriores ao recurso."""
    run_id = session.get('practice_run_record_id')
    run = db.session.get(PracticeRun, run_id) if isinstance(run_id, int) else None
    if run and run.student_id == student_id and run.ended_at is None:
        return run
    started_iso = session.get('practice_started_at')
    started = datetime.fromisoformat(started_iso) if started_iso else datetime.now(timezone.utc)
    if started.tzinfo is None:
        started = started.replace(tzinfo=timezone.utc)
    run = PracticeRun(student_id=student_id, started_at=started)
    db.session.add(run)
    db.session.commit()
    session['practice_run_record_id'] = run.id
    session['practice_started_at'] = iso_utc(started)
    return run

def duration_clock(seconds):
    seconds = max(0, int(seconds))
    hours, remainder = divmod(seconds, 3600)
    minutes, secs = divmod(remainder, 60)
    return f'{hours:02d}:{minutes:02d}:{secs:02d}'

class Inspector(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.tags=[]; self.classes=[]; self.links=[]; self.attrs=[]; self.texts=[]
        self._link=False
        self.nodes=[]; self._stack=[]
        self._voids={'area','base','br','col','embed','hr','img','input','link','meta','param','source','track','wbr'}
    def handle_starttag(self, tag, attrs):
        a=dict(attrs)
        self.tags.append(tag)
        self.attrs.append((tag,a))
        self.classes.extend((a.get('class') or '').split())
        node={'tag':tag,'attrs':a,'parent':self._stack[-1] if self._stack else None}
        self.nodes.append(node)
        if tag not in self._voids: self._stack.append(node)
        if tag=='a': self._link=True
    def handle_endtag(self, tag):
        for index in range(len(self._stack)-1,-1,-1):
            if self._stack[index]['tag']==tag:
                del self._stack[index:]
                break
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

def check_submission(source, fw, exercise, variant, return_details=False):
    """Avalia cada atividade utilizando critérios registrados no servidor."""
    doc=Inspector()
    try: doc.feed(source)
    except Exception:
        error=['HTML não pôde ser analisado.']
        return (False,error,[]) if return_details else (False,error)
    sample=(REFERENCES['navSamples'][fw][variant] if exercise==0 else REFERENCES['lessonCodeExamples'][fw][exercise])
    clean_sample=normalized_html(sample)
    clean_user=normalized_html(source)
    if clean_sample==clean_user or (len(clean_sample)>60 and clean_sample in clean_user):
        error=['Não é permitido enviar uma cópia integral do código de referência.']
        return (False,error,[]) if return_details else (False,error)
    tags=doc.tags; classes=set(doc.classes); a=doc.attrs
    html_class=lambda item: set(item.get('class','').split())
    def valid_grid_items():
        grids=[node for node in doc.nodes
               if node['tag'] in ('div','main','section')
               and ('grid' if fw=='tailwind' else 'row') in (node['attrs'].get('class') or '').split()]
        for grid in grids:
            columns=0
            for node in doc.nodes:
                if node['parent'] is not grid or node['tag'] not in ('div','article'):
                    continue
                cl=set((node['attrs'].get('class') or '').split())
                if fw=='tailwind' or (fw=='bootstrap' and any(x.startswith('col-') or x=='col' for x in cl)) or (fw=='materialize' and 'col' in cl):
                    columns+=1
            if columns>=3:
                return True
        return False
    text=' '.join(doc.texts).lower()
    has=lambda tag:tag in tags
    regex=lambda pattern:bool(re.search(pattern, ' '.join(doc.classes), re.I))
    palette={'red','pink','purple','deep-purple','indigo','blue','light-blue','cyan','teal','green','light-green','lime','yellow','amber','orange','deep-orange','brown','grey','blue-grey'}
    background_valid=(regex(r'\bbg-(?:primary|secondary|success|danger|warning|info|light|dark|body)\b') if fw=='bootstrap'
                     else bool(classes & palette) if fw=='materialize'
                     else regex(r'\bbg-(?:white|black|transparent|[a-z]+-(?:50|[1-9]00|950))\b'))
    button_valid=(('btn' in classes and any(x.startswith('btn-') for x in classes)) if fw=='bootstrap'
                  else ('btn' in classes or 'btn-large' in classes) if fw=='materialize'
                  else regex(r'\bbg-[\w-]+\b') and regex(r'\bpx-[\w-]+\b'))
    criteria=[]
    if exercise==0:
        targets={v.get('id') for t,v in a if v.get('id')}
        triggers=[v for t,v in a if t in ('button','a') and
                  any(k in v for k in ('data-target','data-bs-target','aria-controls'))]
        linked_menu=any((v.get('data-target') or v.get('data-bs-target') or
                        v.get('aria-controls') or '').lstrip('#') in targets for v in triggers)
        criteria=[(has('nav') or has('header'),'Criar estrutura de navegação'),
                  (any(t=='a' and v.get('href') and len(v.get('href'))>0 for t,v in a)
                   and len(text.strip())>5,'Adicionar marca com link'),
                  (bool(triggers),'Criar botão de abertura do menu'),
                  (linked_menu,'Associar botão à área do menu')]
        if variant=='side':
            criteria.append((any('sidenav' in c or 'offcanvas' in c for c in classes) or has('aside'),
                             'Criar painel lateral'))
    elif exercise==1:
        criteria=[(has('section'),'Criar seção'),(any(t in tags for t in ['h1','h2','h3','h4','h5','h6']),'Adicionar título'),(background_valid,'Aplicar classe de cor')]
    elif exercise==2:
        criteria=[(regex(r'\b(grid|row)\b'),'Criar grid'),
                  (valid_grid_items(),'Criar pelo menos três colunas lado a lado'),
                  (regex(r'(?:sm:|md:|lg:|xl:|col-(?:sm|md|lg|xl|xxl)-|\bm\d+\b|\bl\d+\b)'),'Aplicar responsividade')]
    elif exercise==3:
        criteria=[(has('button'),'Criar botão'),(button_valid,'Aplicar classe de botão/cor'),(any(len(re.sub(r'<[^>]+>', '', button).strip()) > 2 for button in re.findall(r'<button\b[^>]*>(.*?)</button\s*>', source, re.I | re.S)),'Adicionar texto de ação')]
    elif exercise==4:
        criteria=[(regex(r'\bcard\b|\bcard-panel\b|\bshadow(?:-[\w-]+)?\b'),'Criar card'),(any(t in tags for t in ['h1','h2','h3','h4','h5','h6']) or 'card-title' in classes,'Adicionar título'),(has('p'),'Adicionar descrição')]
    elif exercise==5:
        criteria=[(has('form'),'Criar formulário'),(any(t=='input' and d.get('type')=='text' for t,d in a) and any(t=='input' and d.get('type')=='email' for t,d in a),'Incluir nome e e-mail'),(any(t in ('button','input') and d.get('type')=='submit' for t,d in a),'Adicionar envio')]
    elif exercise==6:
        criteria=[(any(t in tags for t in ['h1','h2','h3','h4','h5','h6']),'Adicionar título'),(has('p'),'Adicionar parágrafo'),(regex(r'flow-text|text-|fs-|fw-|font-|center-align'),'Estilizar tipografia')]
    elif exercise==7:
        criteria=[(has('section'),'Criar seção'),(any(t in tags for t in ['h1','h2','h3','h4','h5','h6']),'Adicionar título'),(regex(r'\b(p-|m-|py-|px-|my-|mx-|section|container)'),'Aplicar espaçamento')]
    elif exercise==8:
        criteria=[(has('img'),'Inserir imagem'),(any(t=='img' and d.get('alt','').strip() for t,d in a),'Adicionar texto alternativo'),(regex(r'img-fluid|responsive-img|w-full|max-w-full'),'Tornar imagem responsiva')]
    elif exercise==9:
        criteria=[(has('ul') or has('ol'),'Criar lista'),(tags.count('li')>=3,'Adicionar 3 itens'),(regex(r'collection|list-group|divide-|border'),'Estilizar lista')]
    elif exercise==10:
        criteria=[(has('p') or has('div'),'Criar mensagem'),(len(text.strip())>=12,'Adicionar texto'),(regex(r'alert|card-panel|bg-|border'),'Aplicar destaque')]
    elif exercise==11:
        criteria=[(has('table'),'Criar tabela'),(has('thead') and has('th'),'Adicionar cabeçalho'),(tags.count('tr')>=3,'Adicionar duas linhas'),(regex(r'table|striped|highlight|border'),'Estilizar tabela')]
    elif exercise==12:
        criteria=[(any(t in tags for t in ['h1','h2','h3','h4','h5','h6']),'Adicionar título'),(regex(r'text-center|center-align|justify-center|valign-wrapper'),'Alinhar conteúdo'),(tags.count('span')>=2 or tags.count('div')>=2,'Criar dois elementos')]
    else:
        criteria=[(has('footer'),'Criar rodapé'),('©' in source or 'copyright' in text,'Adicionar copyright'),(has('a'),'Incluir link'),(regex(r'page-footer|bg-|p-|text-'),'Aplicar estilo')]
    misses=[label for ok,label in criteria if not ok]
    # Comparison against commented examples is also performed in the client UI.
    if len(re.sub(r'\s+','',source))<100:
        misses.append('Código incompleto')
        criteria.append((False,'Código incompleto'))
    details=[{'label':label,'ok':bool(ok)} for ok,label in criteria]
    return (not misses,misses,details) if return_details else (not misses,misses)

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
    # Cada identificação inicia uma rodada limpa, sem excluir o histórico anterior.
    session.pop('teacher', None)
    session['student_id']=student.id
    session['practice_started_at']=datetime.now(timezone.utc).isoformat()
    session.pop('practice_run_record_id', None)
    ensure_practice_run(student.id)
    register_student_access(student.id)
    return jsonify(student={'name':student.name,'enrollment':student.enrollment,'course':student.course}, progress=progress_of(student.id))

def progress_of(student_id):
    """Progresso da rodada de login atual. Histórico de Award permanece preservado."""
    started_iso=session.get('practice_started_at')
    if not started_iso:
        session['practice_started_at']=datetime.now(timezone.utc).isoformat()
        started_iso=session['practice_started_at']
    started=datetime.fromisoformat(started_iso)
    completed=(db.session.query(Submission.framework, Submission.exercise)
               .filter(Submission.student_id == student_id,
                       Submission.passed.is_(True),
                       Submission.submitted_at >= started)
               .distinct().all())
    return {'points':len(completed),
            'completed':[{'framework':fw,'exercise':exercise} for fw,exercise in completed],
            'run_id':started_iso, 'timer_started_at':started_iso}

@app.post('/api/student/logout')
@student_only
def student_logout():
    # Encerra somente a identificação do aluno. Os resultados permanecem no banco.
    student_id = session.pop('student_id', None)
    run_id = session.pop('practice_run_record_id', None)
    if isinstance(run_id, int):
        run = db.session.get(PracticeRun, run_id)
        if run and run.student_id == student_id and run.ended_at is None:
            run.ended_at = datetime.now(timezone.utc)
            db.session.commit()
    session.pop('practice_started_at', None)
    return jsonify(ok=True)

@app.get('/api/student/me')
@student_only
def me():
    student=db.session.get(Student,session['student_id'])
    if not student:return jsonify(error='Aluno não encontrado.'),404
    if not session.get('practice_started_at'):
        session['practice_started_at']=datetime.now(timezone.utc).isoformat()
    ensure_practice_run(student.id)
    register_student_access(student.id)
    return jsonify(student={'name':student.name,'enrollment':student.enrollment,'course':student.course},progress=progress_of(student.id))

@app.post('/api/submissions')
@student_only
def submit():
    data=request.get_json(silent=True) or {}
    code=data.get('code',''); fw=data.get('framework'); ex=data.get('exercise'); variant=data.get('variant','top')
    if not isinstance(code,str) or len(code)>100_000 or fw not in ('bootstrap','tailwind','materialize') or type(ex)!=int or not 0<=ex<14 or variant not in ('top','side'):
        return jsonify(error='Dados do exercício inválidos.'),400
    passed,missing,criteria=check_submission(code,fw,ex,variant,return_details=True)
    feedback='Concluído' if passed else 'Pendências: '+', '.join(missing)
    run=ensure_practice_run(session['student_id'])
    submitted_now=datetime.now(timezone.utc)
    obj=Submission(student_id=session['student_id'],framework=fw,exercise=ex,variant=variant,code=code,passed=passed,score=1 if passed else 0,feedback=feedback,submitted_at=submitted_now)
    db.session.add(obj)
    if passed:
        run.last_approved_at=submitted_now
    if passed and not Award.query.filter_by(student_id=session['student_id'],framework=fw,exercise=ex).first():
        db.session.add(Award(student_id=session['student_id'],framework=fw,exercise=ex))
    db.session.commit()
    return jsonify(passed=passed,missing=missing,criteria=criteria,progress=progress_of(session['student_id']))

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
        progress=progress_of(s.id)
        per_framework={fw:{'completed':sum(x['framework']==fw for x in progress['completed']),
                           'attempts':sum(x.framework==fw for x in attempts)}
                       for fw in ('bootstrap','tailwind','materialize')}
        access_info=db.session.query(func.count(StudentAccess.id),func.max(StudentAccess.accessed_at)).filter(
            StudentAccess.student_id==s.id).one()
        data.append({'access_count':access_info[0], 'last_access':iso_utc(access_info[1]),
                     'id':s.id,'name':s.name,'enrollment':s.enrollment,'course':s.course,'points':progress['points'],
                     'completed':progress['completed'],'attempts':len(attempts),
                     'frameworks_practiced':[fw for fw,p in per_framework.items() if p['attempts']>0],
                     'framework_progress':per_framework,
                     'last_attempt':iso_utc(attempts[0].submitted_at) if attempts else None})
    return jsonify(students=data)

# Classificação do dia civil de Fortaleza; a pontuação acumulada permanece intacta.
# Cada aluno pontua uma vez por framework/exercício aprovado no dia.
RANKING_TIMEZONE = ZoneInfo('America/Fortaleza')

@app.get('/api/ranking/today')
@student_only
def student_daily_ranking():
    day = datetime.now(RANKING_TIMEZONE).date()
    beginning = datetime.combine(day, time.min, tzinfo=RANKING_TIMEZONE).astimezone(timezone.utc)
    ending = datetime.combine(day + timedelta(days=1), time.min, tzinfo=RANKING_TIMEZONE).astimezone(timezone.utc)

    approved = (db.session.query(Submission.student_id, Submission.framework, Submission.exercise)
                .filter(Submission.passed.is_(True),
                        Submission.submitted_at >= beginning,
                        Submission.submitted_at < ending)
                .group_by(Submission.student_id, Submission.framework, Submission.exercise).all())
    scores = {}
    for student_id, _framework, _exercise in approved:
        scores[student_id] = scores.get(student_id, 0) + 1

    # Tempo de execução = início da rodada até a última resposta aprovada do dia,
    # somando rodadas distintas, com corte no início e no fim do dia de Fortaleza.
    elapsed = {}
    runs = (PracticeRun.query.filter(PracticeRun.student_id.in_(list(scores)),
                                     PracticeRun.last_approved_at >= beginning,
                                     PracticeRun.last_approved_at < ending).all()
            if scores else [])
    for run in runs:
        started = run.started_at.replace(tzinfo=timezone.utc) if run.started_at.tzinfo is None else run.started_at
        approved_at = (run.last_approved_at.replace(tzinfo=timezone.utc)
                       if run.last_approved_at.tzinfo is None else run.last_approved_at)
        seconds = max(0, int((min(approved_at, ending) - max(started, beginning)).total_seconds()))
        elapsed[run.student_id] = elapsed.get(run.student_id, 0) + seconds

    students = Student.query.filter(Student.id.in_(scores.keys())).all() if scores else []
    students.sort(key=lambda student: (-scores[student.id], elapsed.get(student.id, 0),
                                        student.name.casefold(), student.id))
    entries = []
    position = 0
    last_score = None
    for index, student in enumerate(students, 1):
        points = scores[student.id]
        if points != last_score:
            position = index
        entries.append({'position': position, 'student_id': student.id,
                        'name': student.name, 'course': student.course, 'points': points,
                        'duration_seconds': elapsed.get(student.id, 0),
                        'duration': duration_clock(elapsed.get(student.id, 0))})
        last_score = points
    return jsonify(date=day.isoformat(), timezone='America/Fortaleza', ranking=entries)

@app.get('/api/teacher/student/<int:student_id>')
@teacher_only
def student_attempts(student_id):
    s=db.session.get(Student,student_id)
    if not s:return jsonify(error='Aluno não encontrado.'),404
    rows=Submission.query.filter_by(student_id=student_id).order_by(Submission.submitted_at.desc()).limit(200).all()
    access_rows=StudentAccess.query.filter_by(student_id=student_id).order_by(StudentAccess.accessed_at.desc()).limit(50).all()
    return jsonify(name=s.name,accesses=[iso_utc(x.accessed_at) for x in access_rows],attempts=[{'framework':x.framework,'exercise':x.exercise+1,'variant':x.variant,'passed':x.passed,'feedback':x.feedback,'code':x.code,'at':iso_utc(x.submitted_at)} for x in rows])

@app.get('/api/teacher/export.csv')
@teacher_only
def export_csv():
    out=io.StringIO();w=csv.writer(out)
    w.writerow(['Nome','Matrícula','Curso','Frameworks praticados','Bootstrap (concluídos)','Tailwind (concluídos)','Materialize (concluídos)','Pontuação','Atividades concluídas','Último acesso (UTC)','Total de acessos'])
    for s in Student.query.order_by(Student.name):
        p=progress_of(s.id)
        attempted={fw for (fw,) in db.session.query(Submission.framework).filter_by(student_id=s.id).distinct().all()}
        counts={fw:sum(item['framework']==fw for item in p['completed']) for fw in ('bootstrap','tailwind','materialize')}
        w.writerow([s.name,s.enrollment,s.course,', '.join(fw for fw in ('bootstrap','tailwind','materialize') if fw in attempted),
                    counts['bootstrap'],counts['tailwind'],counts['materialize'],p['points'],len(p['completed']),
                    iso_utc(db.session.query(func.max(StudentAccess.accessed_at)).filter_by(student_id=s.id).scalar()),
                    db.session.query(func.count(StudentAccess.id)).filter_by(student_id=s.id).scalar()])
    return Response('\ufeff'+out.getvalue(),mimetype='text/csv; charset=utf-8',headers={'Content-Disposition':'attachment; filename="resultados_framework_academy.csv"'})

# Cria apenas tabelas inexistentes (incluindo o log de acessos).
# Não remove nem substitui tabelas/dados existentes.
with app.app_context():
    db.create_all()

if __name__=='__main__':
    app.run(port=int(os.getenv('PORT','5000')),debug=os.getenv('FLASK_DEBUG')=='1')
