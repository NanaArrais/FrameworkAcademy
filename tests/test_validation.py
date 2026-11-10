"""Regressão: 42 combinações, menu lateral, respostas inválidas e histórico de acessos.

Execute: python -m unittest discover -s tests -v
Os testes utilizam SQLite em memória e NUNCA se conectam ao PostgreSQL do Render.
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["COOKIE_SECURE"] = "false"

from werkzeug.security import generate_password_hash
from app import app, db, check_submission, Student, StudentAccess, Award


def solution(index, framework, variant="top"):
    """Solução independente de cada exercício, sem copiar o modelo didático."""
    bg = {"bootstrap": "bg-primary", "tailwind": "bg-green-600", "materialize": "blue"}[framework]
    button = {"bootstrap": "btn btn-primary", "tailwind": "bg-green-600 px-4 py-2", "materialize": "btn waves-effect"}[framework]
    responsive = {"bootstrap": "col-12 col-md-4", "tailwind": "rounded shadow p-4", "materialize": "col s12 m4"}[framework]
    if variant == "side" and index == 0:
        body = ('<nav><a href="#inicio">Portal dos Estudantes</a>'
                '<button aria-controls="painel">Abrir</button></nav>'
                '<aside id="painel" class="sidenav"><a href="#cursos">Cursos</a></aside>')
    else:
        parts = [
            '<nav><a href="#inicio">Portal Acadêmico Digital</a>'
            '<button type="button" aria-controls="menu-academia">Abrir menu</button>'
            '<div id="menu-academia"><a href="#cursos">Cursos</a></div></nav>',
            f'<section class="{bg}"><h4>Portal de Aprendizagem</h4></section>',
            ('<div class="row grid md:grid-cols-3">'
             + ''.join(f'<div class="{responsive}"><div class="card">Curso {n}</div></div>' for n in range(3))
             + '</div>'),
            f'<button class="{button}">Confirmar matrícula</button>',
            '<article class="card shadow"><h3>Curso digital</h3><p>Descrição do curso.</p></article>',
            ('<form><label>Nome<input type="text" required></label>'
             '<label>E-mail<input type="email" required></label>'
             '<button type="submit">Enviar inscrição</button></form>'),
            '<h3 class="fs-2 flow-text text-2xl font-bold">Meu título</h3><p>Texto principal.</p>',
            '<section class="section container p-4 my-4"><h4>Área espaçada</h4></section>',
            '<img src="https://example.org/paisagem.png" alt="Paisagem ilustrativa" class="img-fluid responsive-img max-w-full">',
            '<ul class="collection list-group border"><li>Primeiro</li><li>Segundo</li><li>Terceiro</li></ul>',
            '<div class="alert card-panel bg-green-100"><p>Operação concluída com sucesso.</p></div>',
            ('<table class="table striped border"><thead><tr><th>Curso</th></tr></thead>'
             '<tbody><tr><td>HTML</td></tr><tr><td>CSS</td></tr></tbody></table>'),
            '<section class="text-center center-align"><h4>Equipe</h4><div><span>Primeiro</span><span>Segundo</span></div></section>',
            '<footer class="page-footer bg-dark p-4">© 2026 Escola <a href="#contato">Contato</a></footer>',
        ]
        body = parts[index]
    return ('<!doctype html><html lang="pt-BR"><head><meta charset="utf-8">'
            '<title>Exercício autoral</title></head><body>'+body+'</body></html>')


class ValidationTests(unittest.TestCase):
    def test_all_42_framework_and_exercise_combinations(self):
        for framework in ("bootstrap", "tailwind", "materialize"):
            for exercise in range(14):
                with self.subTest(framework=framework, exercise=exercise+1):
                    passed, missing = check_submission(solution(exercise, framework), framework, exercise, "top")
                    self.assertTrue(passed, str(missing))

    def test_all_side_navigation_variants(self):
        for framework in ("bootstrap", "tailwind", "materialize"):
            with self.subTest(framework=framework):
                passed, missing = check_submission(solution(0, framework, "side"), framework, 0, "side")
                self.assertTrue(passed, str(missing))

    def test_server_criteria_match_passed(self):
        for framework in ("bootstrap", "tailwind", "materialize"):
            for exercise in range(14):
                passed, missing, criteria = check_submission(solution(exercise, framework), framework, exercise, "top", return_details=True)
                with self.subTest(framework=framework, exercise=exercise+1):
                    self.assertEqual(passed, not missing)
                    self.assertTrue(criteria)
                    self.assertTrue(all(c["ok"] for c in criteria), str(criteria))

    def test_navigation_requires_mobile_toggle_and_linked_target(self):
        html='<html><body><nav><a href="#inicio">Portal de cursos</a></nav></body></html>'
        passed, missing=check_submission(html,"bootstrap",0,"top")
        self.assertFalse(passed)
        self.assertIn("Criar botão de abertura do menu",missing)
        self.assertIn("Associar botão à área do menu",missing)

    def test_form_rejects_missing_email(self):
        invalid = ('<form><input type="text"><input type="text">'
                   '<button type="submit">Enviar</button></form>' + '<!-- teste -->' * 10)
        passed, missing = check_submission(invalid, "bootstrap", 5, "top")
        self.assertFalse(passed)
        self.assertIn("Incluir nome e e-mail", missing)

    def test_grid_requires_three_items(self):
        for framework in ("bootstrap", "tailwind", "materialize"):
            wrapper = {
                "bootstrap": '<div class="row"><div class="col-12 col-md-4"><div class="card">A</div></div></div>',
                "materialize": '<div class="row"><div class="col s12 m4"><div class="card-panel">A</div></div></div>',
                "tailwind": '<div class="grid md:grid-cols-3"><div class="shadow">A</div></div>',
            }[framework]
            invalid='<html><body>'+wrapper+'</body></html>'+' ' * 100
            passed, missing=check_submission(invalid, framework, 2, "top")
            self.assertFalse(passed)
            self.assertIn("Criar pelo menos três colunas lado a lado", missing)

    def test_nested_grid_columns_are_rejected(self):
        for framework in ("bootstrap", "materialize", "tailwind"):
            col={
                "bootstrap": "col-12 col-md-4",
                "materialize": "col s12 m4",
                "tailwind": "rounded shadow",
            }[framework]
            root="grid md:grid-cols-3" if framework=="tailwind" else "row"
            # Três colunas no total, mas aninhadas: não formam três irmãs.
            markup=('<div class="'+root+'"><div class="'+col+'">'
                    '<div class="'+col+'">Interno</div>'
                    '<div class="'+col+'">Interno</div>'
                    '</div></div>')
            passed,missing=check_submission('<html><body>'+markup+'</body></html>',framework,2,"top")
            self.assertFalse(passed,framework)
            self.assertIn("Criar pelo menos três colunas lado a lado",missing)

    def test_rejects_style_from_another_framework(self):
        html=('<html><body><section class="blue"><h2>Minha seção</h2></section>'
              '</body></html>')
        passed,missing=check_submission(html,"bootstrap",1,"top")
        self.assertFalse(passed)
        self.assertIn("Aplicar classe de cor",missing)

    def test_h4_and_card_title_supported(self):
        passed, missing = check_submission(
            '<article class="card"><div class="card-content"><span class="card-title">Título</span>'
            '<p>Descrição do item apresentado ao aluno.</p></div></article>',
            "materialize", 4, "top")
        self.assertTrue(passed, str(missing))

    def test_reference_examples_match_stated_grid_and_form_requirements(self):
        from app import REFERENCES
        for framework in ("bootstrap", "materialize", "tailwind"):
            grid=REFERENCES["lessonCodeExamples"][framework][2]
            form=REFERENCES["lessonCodeExamples"][framework][5]
            self.assertEqual(grid.count("Bloco "), 3, framework)
            self.assertIn("<form", form, framework)
            self.assertIn('type="email"', form, framework)
            self.assertIn('type="text"', form, framework)
            self.assertIn('type="submit"', form, framework)

    def test_access_log_and_teacher_result(self):
        os.environ["TEACHER_PASSWORD_HASH"] = generate_password_hash("senha-de-teste")
        with app.app_context():
            db.drop_all()
            db.create_all()
        with app.test_client() as client:
            reply=client.post("/api/student/register", json={
                "name":"Estudante Demonstração", "enrollment":"MAT000987", "course":"ADS"})
            self.assertEqual(reply.status_code, 200)
            self.assertEqual(client.get("/api/student/me").status_code, 200)
            self.assertEqual(client.post("/api/teacher/login",json={"password":"senha-de-teste"}).status_code,200)
            results=client.get("/api/teacher/results")
            self.assertEqual(results.status_code,200)
            student=results.get_json()["students"][0]
            self.assertEqual(student["access_count"], 2)
            self.assertIsNotNone(student["last_access"])
            details=client.get("/api/teacher/student/"+str(student["id"]))
            self.assertEqual(len(details.get_json()["accesses"]),2)
        with app.app_context():
            self.assertEqual(StudentAccess.query.count(),2)
            self.assertEqual(Student.query.count(),1)
            self.assertEqual(Award.query.count(),0)

    def test_student_logout_allows_switch_without_deleting_results(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
        with app.test_client() as client:
            first = client.post("/api/student/register", json={
                "name": "Primeiro Aluno", "enrollment": "SWITCH001", "course": "ADS"})
            self.assertEqual(first.status_code, 200)
            with app.app_context():
                first_id = Student.query.filter_by(enrollment="SWITCH001").first().id
                db.session.add(Award(student_id=first_id, framework="materialize", exercise=1))
                db.session.commit()
            self.assertEqual(client.get("/api/student/me").get_json()["progress"]["points"], 1)
            self.assertEqual(client.post("/api/student/logout").status_code, 200)
            self.assertEqual(client.get("/api/student/me").status_code, 401)
            self.assertEqual(client.get("/api/ranking/today").status_code, 401)
            second = client.post("/api/student/register", json={
                "name": "Segundo Aluno", "enrollment": "SWITCH002", "course": "Jogos Digitais"})
            self.assertEqual(second.status_code, 200)
            self.assertEqual(second.get_json()["progress"]["points"], 0)
            self.assertEqual(client.get("/api/student/me").get_json()["student"]["enrollment"], "SWITCH002")
            with app.app_context():
                self.assertEqual(Student.query.count(), 2)
                self.assertEqual(Award.query.filter_by(student_id=first_id).count(), 1)
            self.assertEqual(client.post("/api/student/logout").status_code, 200)

    def test_student_switch_controls_and_scoped_home_styling(self):
        html=(ROOT/"templates"/"index.html").read_text(encoding="utf-8")
        for element_id in ("studentSessionMenu","sessionStudentName","studentLogoutHeader","studentSwitchPractice"):
            self.assertEqual(html.count('id="'+element_id+'"'),1,element_id)
        self.assertIn("async function faSwitchStudent()",html)
        self.assertIn("await api('/api/student/logout'",html)
        self.assertIn("window.location.assign('/?trocar-aluno=1')",html)
        self.assertIn("document.getElementById('studentSessionMenu').hidden=false",html)
        self.assertIn("#view-learn .introhero",html)
        self.assertIn("faDraftStorageKey()",html)

    def test_submit_api_all_42_awards_one_point_each_and_no_double_count(self):
        with app.app_context():
            db.drop_all()
            db.create_all()
        with app.test_client() as client:
            registration=client.post("/api/student/register",json={
                "name":"Aluno de Integração", "enrollment":"INT00001", "course":"ADS"
            })
            self.assertEqual(registration.status_code,200,registration.get_json())
            count=0
            for fw in ("bootstrap","tailwind","materialize"):
                for ex in range(14):
                    payload={"code":solution(ex,fw),"framework":fw,"exercise":ex,"variant":"top"}
                    result=client.post("/api/submissions",json=payload)
                    self.assertEqual(result.status_code,200,(fw,ex,result.get_json()))
                    body=result.get_json()
                    self.assertTrue(body["passed"],(fw,ex,body["missing"]))
                    count+=1
                    self.assertEqual(body["progress"]["points"],count)
                    self.assertEqual(len(body["progress"]["completed"]),count)
            repeated=client.post("/api/submissions",json={
                "code":solution(0,"materialize"),"framework":"materialize","exercise":0,"variant":"top"
            })
            self.assertEqual(repeated.status_code,200)
            self.assertEqual(repeated.get_json()["progress"]["points"],42)
            self.assertEqual(len(repeated.get_json()["progress"]["completed"]),42)
            with app.app_context():
                self.assertEqual(Award.query.count(),42)

    def test_teacher_dashboard_filters_and_layout(self):
        html=(ROOT/"templates"/"index.html").read_text(encoding="utf-8")
        for element_id in (
            "teacherFilterCourse","teacherFilterFramework","teacherFilterStatus",
            "teacherFilterSince","teacherFilterSort","teacherClearFilters",
            "teacherResultCount","teacherSearch","teacherRows"
        ):
            self.assertEqual(html.count('id="'+element_id+'"'),1,element_id)
        self.assertIn('class="teacher-panel-toolbar"',html)
        self.assertIn('class="teacher-filter-panel"',html)
        self.assertIn("filters.sort==='recent'",html)
        self.assertIn("faMatchesTeacher(student,filters)",html)
        self.assertIn('class="teacher-progress"',html)

    def test_copy_blocked_alert_visible_over_fullscreen(self):
        html=(ROOT/"templates"/"index.html").read_text(encoding="utf-8")
        self.assertIn('z-index:30050',html)
        self.assertIn('role="alert" aria-live="assertive"',html)
        self.assertIn("toast-warning",html)
        self.assertIn("Não é permitido copiar e colar o exemplo.",html)

    def test_interface_wiring(self):
        html = (ROOT/"templates"/"index.html").read_text(encoding="utf-8")
        for marker in (
            "document.querySelector('.framework-options').addEventListener",
            "$('#lessonList').addEventListener",
            "function faRenderDockLibrary()",
            "faLoadDraftState",
            "faSaveDraftState",
            'id="lessonReferenceContext"',
            'id="teacherFilterFramework"',
            'id="teacherFilterStatus"',
            'id="teacherFilterCourse"',
            'id="teacherFilterSince"',
            "result.criteria",
            "faAccessDate(",
        ):
            self.assertIn(marker,html)
        for id_ in ("lessonRun","lessonCode","lessonFramework","lessonDockToggle","lessonMaxWorkspace"):
            self.assertEqual(html.count(f'id="{id_}"'),1)


if __name__ == "__main__":
    unittest.main()
