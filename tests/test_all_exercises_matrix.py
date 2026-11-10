"""Matriz de regressão por questão e framework: acertos, erros e cópia."""
import unittest

from test_validation import solution
from app import check_submission, REFERENCES

FRAMEWORKS = ("bootstrap", "tailwind", "materialize")

def missing_required_feature(code, exercise):
    """Altera uma condição essencial na solução correta sem tocar nas demais."""
    if exercise == 0:
        return code.replace("<nav>", "<section>").replace("</nav>", "</section>")
    if exercise == 1:
        return code.replace("<section ", "<article ").replace("</section>", "</article>")
    if exercise == 2:
        return code.replace("Curso 2", "").replace("Curso 3", "").replace(
            '<div class="card">', '<div class="card">', 1
        ).replace('<div class="card">Curso 1</div>', '<div class="card">Curso 1</div>')
    if exercise == 3:
        return code.replace("<button ", "<span ").replace("</button>", "</span>")
    if exercise == 4:
        return code.replace("<p>Descrição do curso.</p>", "<div>Descrição do curso.</div>")
    if exercise == 5:
        return code.replace('type="email"', 'type="text"')
    if exercise == 6:
        return code.replace("<p>Texto principal.</p>", "<div>Texto principal.</div>")
    if exercise == 7:
        return code.replace("<section ", "<article ").replace("</section>", "</article>")
    if exercise == 8:
        return code.replace('alt="Paisagem ilustrativa"', 'alt=""')
    if exercise == 9:
        return code.replace("<li>", "<span>").replace("</li>", "</span>")
    if exercise == 10:
        return code.replace('class="alert card-panel bg-green-100"', 'class="plain"')
    if exercise == 11:
        return code.replace("<thead>", "<tbody>").replace("</thead>", "</tbody>").replace("<th>", "<td>").replace("</th>", "</td>")
    if exercise == 12:
        return code.replace("<span>", "<em>").replace("</span>", "</em>")
    if exercise == 13:
        return code.replace("<footer ", "<section ").replace("</footer>", "</section>")
    raise AssertionError(exercise)

class AllExercisesMatrix(unittest.TestCase):
    def test_each_valid_solution_scores_and_has_all_criteria(self):
        checked = 0
        for framework in FRAMEWORKS:
            for index in range(14):
                with self.subTest(framework=framework, question=index+1):
                    passed, missing, criteria = check_submission(
                        solution(index, framework), framework, index, "top", True)
                    self.assertTrue(passed, missing)
                    self.assertEqual(missing, [])
                    self.assertTrue(criteria and all(c["ok"] for c in criteria), criteria)
                    checked += 1
        self.assertEqual(checked, 42)

    def test_each_blank_solution_is_rejected_with_diagnostics(self):
        for framework in FRAMEWORKS:
            for index in range(14):
                with self.subTest(framework=framework, question=index+1):
                    passed, missing, criteria = check_submission(
                        "<!doctype html><html><head></head><body></body></html>",
                        framework, index, "top", True)
                    self.assertFalse(passed)
                    self.assertTrue(missing)
                    self.assertTrue(any(not item["ok"] for item in criteria))

    def test_all_42_reference_samples_cannot_be_submitted_verbatim(self):
        for framework in FRAMEWORKS:
            for index in range(14):
                example = (REFERENCES["navSamples"][framework]["top"] if index==0
                           else REFERENCES["lessonCodeExamples"][framework][index])
                with self.subTest(framework=framework, question=index+1):
                    passed, missing = check_submission(example, framework, index, "top")
                    self.assertFalse(passed, "Cópia integral aprovada")
                    self.assertIn("Não é permitido enviar uma cópia integral do código de referência.", missing)

    def test_each_question_rejects_essential_missing_requirement(self):
        # Questions with several required items must never pass if a key requirement
        # is removed; exercise 3 (grid) uses a separate sibling-specific regression.
        for framework in FRAMEWORKS:
            for index in range(14):
                if index==2:
                    continue
                with self.subTest(framework=framework, question=index+1):
                    valid=solution(index,framework)
                    invalid=missing_required_feature(valid,index)
                    self.assertNotEqual(invalid,valid)
                    passed, missing=check_submission(invalid,framework,index,"top")
                    self.assertFalse(passed, (framework,index+1,missing))

    def test_side_menu_for_each_framework_valid_and_missing_panel(self):
        for framework in FRAMEWORKS:
            good=solution(0,framework,"side")
            with self.subTest(framework=framework, case="valid"):
                self.assertTrue(check_submission(good,framework,0,"side")[0])
            with self.subTest(framework=framework, case="missing_sidebar"):
                invalid=good.replace('<aside id="painel" class="sidenav">','<div id="painel">').replace("</aside>","</div>")
                self.assertFalse(check_submission(invalid,framework,0,"side")[0])

if __name__=="__main__":
    unittest.main()
