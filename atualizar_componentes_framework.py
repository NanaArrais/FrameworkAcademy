#!/usr/bin/env python3
"""Patch incremental do Framework Academy (sem substituir banco, tabelas ou dados).
Uso: python atualizar_componentes_framework.py /caminho/Framework_Academy_Portal
Cria cópias .bak e é idempotente.
"""
from pathlib import Path
import argparse, json, re, shutil, sys

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('project',nargs='?',default='.',help='Pasta com app.py, templates/ e reference_samples.json')
args=parser.parse_args()
root=Path(args.project).expanduser().resolve()
app_path=root/'app.py'
html_path=root/'templates'/'index.html'
samples_path=root/'reference_samples.json'
for file in (app_path,html_path,samples_path):
    if not file.is_file():sys.exit(f'ERRO: arquivo não encontrado: {file}')

html=html_path.read_text(encoding='utf-8')
backend=app_path.read_text(encoding='utf-8')
obj=json.loads(samples_path.read_text(encoding='utf-8'))
if 'PATCH_FA_V16' in html:
    print('Este projeto já recebeu a atualização. Nenhuma alteração adicional.')
    sys.exit(0)

# 1. Desafio de menu: nome/marca e estrutura de navegação, sem link obrigatório para Cursos.
old="description:'Crie uma barra de navegação com uma marca e um link para Cursos.'"
assert old in html,'Não foi possível encontrar a descrição original do exercício.'
html=html.replace(old,"description:'Crie uma navegação com nome ou marca e links de sua escolha.'")
html=html.replace("requirements:['nav','brand','link']","requirements:['nav','brand']",1)
html=html.replace("link:'Incluir link para Cursos',",'')
html=html.replace("'Construa um menu lateral: um botão ☰ abre o painel com a marca e o link para Cursos.'","'Construa um menu lateral: um botão ☰ abre o painel com a identidade do site.'")
html=html.replace("'Construa uma barra superior responsiva: em telas menores, os links devem aparecer ao abrir o botão ☰.'","'Construa uma barra superior responsiva: em telas menores, o botão ☰ deve abrir o menu.'")
html=html.replace("['Criar navegação e botão de abertura','Incluir marca e menu lateral','Adicionar link para Cursos']","['Criar navegação e botão de abertura','Incluir marca e menu lateral']")
html=html.replace("'<!-- Exercício: crie aqui uma barra <nav> com marca e link Cursos. -->'","'<!-- Exercício: crie aqui um menu com sua marca. -->'")
html=html.replace("0:['Comece criando a estrutura semântica da barra de navegação.','Insira uma marca (nome do site) e um link cujo texto seja Cursos.','Aplique as classes de navegação do framework e execute para conferir o alinhamento.']","0:['Comece com a estrutura de navegação do framework escolhido.','Adicione o nome do site ou sua marca e configure o alinhamento.','Se optar pelo menu lateral, inclua o botão e conecte-o ao painel pelo identificador correto.']")
# Remover dicas de erro obsoletas mesmo quando trecho vier de versão anterior.
html=html.replace("if(chk.key==='link')detail=lessonIdx===0&&lessonNavVariant==='side'?'Adicione dentro do menu lateral um link <a> com o texto Cursos.':'Adicione dentro de <nav> um link <a> com o texto Cursos.';",'')
# Corrigir verificador local: excluir link de Cursos, mantendo estrutura de menu lateral.
html=html.replace("lessonCatalog[i].requirements.map(k=>({key:k,ok:!!checks[k],label:lessonRequirementsText[k]}))","lessonCatalog[i].requirements.map(k=>({key:k,ok:!!checks[k],label:lessonRequirementsText[k]}))")
# Links Cursos nos modelos de demonstração: remover apenas tags de navegação completas.
html=re.sub(r'<li><a\b[^>]*href=\\?"#cursos\\?"[^>]*>Cursos</a></li>','',html)
html=re.sub(r'<a\b[^>]*href=\\?"#cursos\\?"[^>]*>Cursos</a>','',html)
# Por causa da representação literal em JS template string, removemos linhas vazias de exemplos.
html=html.replace("\n      \n", "\n")
# Evitar o código antigo que inseria um menu pronto quando o aluno selecionava lateral.
start=html.find('// Seleção do menu lateral: inserir MODELO EDITÁVEL')
if start>=0:
    end=html.find('// Painel do professor',start)
    if end>start:
        html=html[:start]+"// O aluno implementa livremente ambos os modelos de navegação.\n"+html[end:]

# 2. Tela cheia: mover a instância DO MESMO iframe do editor para o overlay.
# Antes, #lessonFullFrame.srcdoc recebia cópia separada, propensa a ficar em branco.
old_open="$('#lessonMaxPreview').onclick=()=>{const src=$('#lessonCode').value;$('#lessonFullFrame').srcdoc=exercisePreviewHTML(src);$('#lessonFullPreview').classList.remove('hidden');document.body.classList.add('preview-lock');syncLessonDevice(currentLessonDevice)};"
old_close="function closeLessonFullPreview(){$('#lessonFullPreview').classList.add('hidden');document.body.classList.remove('preview-lock')}"
assert old_open in html and old_close in html,'Não foi localizado o código da prévia anterior.'
new_open="""// PATCH_FA_V16: reutilizar o iframe que já exibe o exercício no editor.
// Assim, tela cheia mostra o MESMO documento, sem segunda prévia vazia.
function openLessonFullPreview(){
 const live=$('#lessonFrame');
 if(!live)return;
 const destination=$('#lessonFullFrameWrap');
 const unused=$('#lessonFullFrame');
 if(unused)unused.remove();
 $('#lessonFullPreview').classList.remove('hidden');
 document.body.classList.add('preview-lock');
 destination.appendChild(live);
 syncLessonDevice(currentLessonDevice);
}
$('#lessonMaxPreview').onclick=openLessonFullPreview;"""
new_close="""function closeLessonFullPreview(){
 const live=$('#lessonFrame');
 const normal=$('#lessonFrameWrap');
 if(live&&normal)normal.appendChild(live);
 $('#lessonFullPreview').classList.add('hidden');
 document.body.classList.remove('preview-lock');
 syncLessonDevice(currentLessonDevice);
}"""
html=html.replace(old_open,new_open).replace(old_close,new_close)

# 3. Backend: remover somente o requisito de link Cursos.
old_server="(any('curso' in s.lower() for s in doc.links),'Adicionar link com texto Cursos')"
assert old_server in backend,'Não foi encontrada a regra do servidor para link Cursos.'
backend=backend.replace(",\n                  "+old_server,"")
# A lista criteria do menu continua válida em ambos os modelos.

# 4. Exemplos de referência: remover somente links Cursos da atividade de navegação.
nav=obj.get('navSamples',{})
for fw, variants in nav.items():
    for style, code in variants.items():
        code=re.sub(r'^[^\n]*<li><a[^\n]*>Cursos</a></li>\n?', '', code, flags=re.M)
        code=re.sub(r'^[^\n]*<a[^\n]*>Cursos</a>\n?', '', code, flags=re.M)
        variants[style]=code
# Código de referência do primeiro exercício: preservar estrutura, remover links explícitos.
for fw, samples in obj.get('lessonCodeExamples',{}).items():
    if samples:
        samples[0]=re.sub(r'^[^\n]*<li><a[^\n]*>Cursos</a></li>\n?', '', samples[0], flags=re.M)
        samples[0]=re.sub(r'^[^\n]*<a[^\n]*>Cursos</a>\n?', '', samples[0], flags=re.M)

# Segurança: backups locais e gravação atômica por arquivo.
for path, content in [(app_path,backend),(html_path,html),(samples_path,json.dumps(obj,ensure_ascii=False,indent=2)+'\n')]:
    backup=path.with_suffix(path.suffix+'.bak')
    if not backup.exists():shutil.copy2(path,backup)
    staged=path.with_suffix(path.suffix+'.tmp')
    staged.write_text(content,encoding='utf-8')
    staged.replace(path)
    print('ATUALIZADO:',path.relative_to(root))
print('\nPronto. Banco de dados, cadastro, notas e estrutura do projeto não foram alterados.')
