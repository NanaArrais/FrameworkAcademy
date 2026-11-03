#!/usr/bin/env python3
"""Atualiza SOMENTE o editor dos exercícios no Framework Academy.
Uso: python atualizar_editor_framework_v17.py /caminho/Framework_Academy_Portal
Requer templates/index.html da aplicação Flask. Não altera PostgreSQL/app.py.
"""
from pathlib import Path
import argparse, shutil, sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('project', nargs='?',default='.',help='Diretório raiz do projeto Flask')
a=parser.parse_args()
path=Path(a.project).expanduser().resolve()/'templates'/'index.html'
if not path.is_file():sys.exit(f'ERRO: não encontrei {path}')
s=path.read_text('utf-8')
if 'FA_EDITOR_V17' in s:
    sys.exit('O editor v17 já está instalado. Nenhuma alteração feita.')
checks=['id="lessonCode"','id="lessonCodeHighlight"','function renderLesson()','function syncLessonSyntax()']
for x in checks:
    if x not in s:sys.exit(f'ERRO: não encontrei {x!r}. Arquivo mantido sem alterações.')

# Editor independente da versão do Flask: CodeMirror 5 via CDN; fallback ao textarea.
head='''<!-- FA_EDITOR_V17: dependências do editor com numeração de linhas -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.css">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/theme/material-darker.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/codemirror.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/xml/xml.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/javascript/javascript.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/css/css.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/mode/htmlmixed/htmlmixed.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closetag.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/codemirror/5.65.16/addon/edit/closebrackets.min.js"></script>
<style>
/* FA_EDITOR_V17: gutter e editor do mesmo tamanho do campo anterior */
.lesson-code-editor .CodeMirror {height: 100%;min-height: 560px;width:100%;font: 13px/1.65 ui-monospace,SFMono-Regular,Consolas,monospace;background:#171d31;color:#e1e8fd}
.lesson-code-editor .CodeMirror-gutters {background:#12192b;border-right:1px solid #38425b}
.lesson-code-editor .CodeMirror-linenumber {color:#94a3b8;padding:0 7px}
.lesson-code-editor .CodeMirror-lines {padding:15px 0}
.lesson-code-editor .CodeMirror-activeline-background {background:rgba(100,116,139,.13)}
.lesson-code-editor .CodeMirror-scroll {min-height:560px}
/* O campo fonte permanece no DOM para os recursos de validação e salvamento. */
.lesson-code-editor:has(.CodeMirror) > #lessonCodeHighlight {display:none}
.lesson-code-editor:has(.CodeMirror) > #lessonCode {display:none!important}
</style>
'''
assert '</head>' in s
s=s.replace('</head>',head+'</head>',1)

# Inserir antes do body, após o JS original, para que renderLesson e handlers existentes estejam prontos.
bridge=r'''<!-- FA_EDITOR_V17: integração CodeMirror com o laboratório existente -->
<script>
(function () {
  const original = document.getElementById('lessonCode');
  if (!original || typeof window.CodeMirror !== 'function') {
    console.warn('CodeMirror indisponível. Mantido o editor anterior; confira o acesso à internet.');
    return;
  }
  const cm = window.CodeMirror.fromTextArea(original, {
    mode: 'htmlmixed',
    theme: 'material-darker',
    lineNumbers: true,
    firstLineNumber: 1,
    lineWrapping: false,
    indentUnit: 2,
    tabSize: 2,
    indentWithTabs: false,
    autoCloseTags: true,
    autoCloseBrackets: true,
    viewportMargin: 20,
    extraKeys: {
      Tab: function(editor) {
        if (editor.somethingSelected()) editor.indentSelection('add');
        else editor.replaceSelection('  ', 'end', '+input');
      },
      'Shift-Tab': function(editor) { editor.indentSelection('subtract'); },
      'Ctrl-Enter': function(editor) { editor.save(); if (typeof runLesson === 'function') runLesson(); },
      'Cmd-Enter': function(editor) { editor.save(); if (typeof runLesson === 'function') runLesson(); },
      'Ctrl-Z': 'undo',
      'Cmd-Z': 'undo',
      'Shift-Ctrl-Z': 'redo',
      'Shift-Cmd-Z': 'redo'
    }
  });
  window.__faCodeMirror = cm;
  cm.on('change', function(editor) {
    // A API e a avaliação já leem #lessonCode.value; mantemos a integração intacta.
    editor.save();
    original.dispatchEvent(new Event('input', { bubbles: true }));
  });
  // Atualiza o editor quando a tela muda de exercício/framework.
  if (typeof renderLesson === 'function') {
    const oldRender = renderLesson;
    renderLesson = function () {
      const result = oldRender.apply(this, arguments);
      if (cm.getValue() !== original.value) cm.setValue(original.value);
      requestAnimationFrame(function () { cm.refresh(); });
      return result;
    };
  }
  // Restaurar muda diretamente o textarea: sincronizar CodeMirror após o clique.
  const resetButton = document.getElementById('lessonReset');
  if (resetButton) resetButton.addEventListener('click', function () {
    queueMicrotask(function () {
      if (cm.getValue() !== original.value) cm.setValue(original.value);
      cm.refresh();
    });
  });
  // Ao entrar em Praticar, garantir que a numeração e a gutter sejam dimensionadas.
  document.querySelectorAll('[data-view="practice"]').forEach(function(button) {
    button.addEventListener('click', function () {
      setTimeout(function () { cm.refresh(); }, 0);
    });
  });
  cm.setValue(original.value);
  cm.refresh();
})();
</script>
'''
assert '</body>' in s
pos=s.rfind('</body>')
s=s[:pos]+bridge+s[pos:]
# CodeMirror handles visual code; legacy highlighter still acts on textarea as data source.
# The small highlighter is hidden through CSS, no destructive changes to JS.
backup=path.with_suffix(path.suffix+'.bak_v17')
shutil.copy2(path,backup)
path.write_text(s,'utf-8')
print(f'OK: editor atualizado: {path}')
print(f'Backup: {backup}')
print('Não foram modificados app.py, tabelas ou dados PostgreSQL.')
print('Reinicie Flask e recarregue com Cmd+Shift+R; conexão à internet necessária para o CDN do editor.')
