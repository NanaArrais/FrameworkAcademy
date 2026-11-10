"""Testes de regressão do Framework Academy (sem acesso ao PostgreSQL real).

Execute: python -m unittest discover -s tests -v
"""
import os
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
# Nunca conecta à base real durante os testes.
os.environ["DATABASE_URL"] = "sqlite:///:memory:"
os.environ["COOKIE_SECURE"] = "false"

from app import check_submission  # noqa: E402


def solution(index, framework):
    """Soluções sintéticas independentes dos exemplos de referência."""
    class_color = {"bootstrap": "bg-primary", "tailwind": "bg-blue-500", "materialize": "blue"}[framework]
    button_color = {"bootstrap": "btn btn-primary", "tailwind": "bg-blue-500 px-4", "materialize": "btn green"}[framework]
    samples = [
        '<nav><a href="#inicio">Portal Acadêmico de Testes</a></nav>',
        f'<section class="{class_color}"><h4>Minha escola digital</h4></section>',
        '<main><div class="row md:grid-cols-3">'
        '<div class="col-md-4 card">Primeiro curso</div>'
        '<div class="col-md-4 card">Segundo curso</div>'
        '<div class="col-md-4 card">Terceiro curso</div></div></main>',
        f'<button class="{button_color}">Confirmado</button>',
        '<article class="card"><h3>Título informativo</h3><p>Descrição personalizada.</p></article>',
        '<form><label>Nome<input type="text"></label><label>E-mail<input type="email"></label>'
        '<button type="submit">Enviar mensagem</button></form>',
        '<h4 class="flow-text">Título legível</h4><p>Texto demonstrativo.</p>',
        '<section class="container"><h4>Área espaçada</h4></section>',
        '<img src="https://example.org/paisagem.png" alt="Paisagem ilustrativa" class="responsive-img">',
        '<ul class="collection"><li>Primeiro</li><li>Segundo</li><li>Terceiro</li></ul>',
        '<div class="card-panel"><p>Operação concluída com sucesso na escola.</p></div>',
        '<table class="striped"><thead><tr><th>Curso</th></tr></thead>'
        '<tbody><tr><td>HTML</td></tr><tr><td>CSS</td></tr></tbody></table>',
        '<section class="center-align"><h4>Itens organizados</h4><span>A</span><span>B</span></section>',
        '<footer class="page-footer">© 2026 Minha Escola <a href="#contato">Contato</a></footer>',
    ]
    return '<!doctype html><html><head><title>Teste autoral</title></head><body>' + samples[index] + '<!-- Exemplo produzido especificamente para regressão; nenhuma solução de referência foi copiada. -->' + '</body></html>'


class ValidationTests(unittest.TestCase):
    def test_all_fourteen_exercises_for_three_frameworks(self):
        for framework in ("bootstrap", "tailwind", "materialize"):
            for exercise in range(14):
                with self.subTest(framework=framework, exercise=exercise + 1):
                    passed, missing = check_submission(solution(exercise, framework), framework, exercise, "top")
                    self.assertTrue(passed, f"{framework} atividade {exercise+1}: {missing}")

    def test_form_requires_text_email_and_submit(self):
        invalid = ('<form><input type="text"><input type="text">'
                   '<button type="submit">Enviar</button></form>' + '<!-- teste -->' * 10)
        passed, missing = check_submission(invalid, "bootstrap", 5, "top")
        self.assertFalse(passed)
        self.assertIn("Incluir nome e e-mail", missing)

    def test_h4_heading_accepted(self):
        passed, missing = check_submission(solution(1, "bootstrap"), "bootstrap", 1, "top")
        self.assertTrue(passed, str(missing))

    def test_ui_integrity_markers(self):
        html = (ROOT / "templates" / "index.html").read_text(encoding="utf-8")
        self.assertNotIn("$document.querySelectorAll", html)
        self.assertIn("document.querySelector('.framework-options').addEventListener", html)
        self.assertIn("$('#lessonList').addEventListener", html)
        self.assertIn("Selecione o framework que deseja praticar", html)
        self.assertIn('id="lessonCode"', html)
        self.assertIn("faSaveDraftState", html)
        self.assertIn("faLoadDraftState", html)
        self.assertIn("document.querySelectorAll('#classGuideContent [data-copy-class]').forEach", html)
        self.assertNotIn("$('[data-copy-class]',$('#classGuideContent')).forEach", html)
        self.assertIn("function renderClassGuide()", html)
        self.assertIn('id="lessonReferenceContext"', html)
        self.assertIn("$('#lessonReferenceContext').textContent", html)
        self.assertIn("Não é permitido copiar e colar o exemplo.", html)
        self.assertIn('id="lessonLibraryDock"', html)
        self.assertIn('id="lessonDockSearch"', html)
        self.assertIn("function faRenderDockLibrary()", html)
        self.assertIn("window.__faAllowClassClipboard?.(code)", html)
        self.assertIn('data-space-mode="code"', html)
        self.assertIn('data-space-mode="preview"', html)
        self.assertEqual(html.count('id="lessonDockToggle"'), 1)
        self.assertEqual(html.count('id="lessonMaxWorkspace"'), 1)
        self.assertEqual(html.count('id="lessonRun"'), 1)


if __name__ == "__main__":
    unittest.main()
