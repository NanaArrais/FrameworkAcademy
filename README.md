# Framework Academy — Portal de Exercícios

Aplicação de ensino de **Bootstrap, Tailwind CSS e Materialize**, agora com backend **Flask + PostgreSQL**.

## Recursos

- Página inicial com apresentação dos três frameworks.
- Menu **Praticar**: aluno informa **nome, matrícula e curso** antes dos exercícios.
- 14 exercícios por framework (42 combinações), com código de referência, editor, visualização e desafios explícitos.
- Exercício de navegação permite escolher **menu superior ou lateral**; Materialize usa `sidenav`, Bootstrap usa `offcanvas` e Tailwind usa classes utilitárias com JavaScript.
- Cada tentativa é salva em `submissions`. A pontuação é conferida e registrada pelo servidor (100 pontos por exercício e framework, uma vez apenas).
- Menu **Resultados do professor**: consulta de todos os alunos, pontos, cursos, matrículas, tentativas, códigos enviados e exportação CSV.
- Menu **Criar** removido da navegação.

## Pré-requisitos

- Python 3.11+ e PostgreSQL 14+.
- Conexão à internet no navegador para carregar Bootstrap, Materialize e Tailwind (CDNs didáticos).

## Configuração local

1. Crie uma base PostgreSQL (exemplo):

   ```sql
   CREATE DATABASE framework_academy;
   ```

2. Na pasta do projeto, crie e ative um ambiente virtual:

   ```bash
   python -m venv .venv
   source .venv/bin/activate          # macOS/Linux
   # .venv\Scripts\activate          # Windows PowerShell
   pip install -r requirements.txt
   ```

3. Gere uma senha **com hash** para o professor:

   ```bash
   python -c "from werkzeug.security import generate_password_hash; import getpass; print(generate_password_hash(getpass.getpass('Senha do professor: ')))"
   ```

4. Configure as variáveis de ambiente (`.env.example` serve apenas como referência; o arquivo `.env` **não é carregado automaticamente**):

   ```bash
   export DATABASE_URL='postgresql+psycopg://usuario:senha@localhost:5432/framework_academy'
   export SECRET_KEY='uma_chave_aleatoria_longa_e_secreta'
   export TEACHER_PASSWORD_HASH='cole_aqui_o_hash_gerado'
   export COOKIE_SECURE=false
   ```

   Para uma chave aleatória: `python -c "import secrets; print(secrets.token_urlsafe(48))"`.
   No Windows PowerShell, use `$env:VARIAVEL = 'valor'` no lugar de `export`.

5. Crie as tabelas e inicie:

   ```bash
   python init_db.py
   python app.py
   ```

6. Acesse **http://localhost:5000**. O arquivo `templates/index.html` **não** deve ser aberto diretamente para usar o banco; abra a URL do Flask.

## Publicar no Render (exemplo)

- Crie um serviço PostgreSQL e configure a `DATABASE_URL` do banco.
- Crie um serviço Web (Python) a partir da pasta deste projeto.
- Build: `pip install -r requirements.txt`
- Pre-deploy (ou primeira execução manual): `python init_db.py`
- Start: `gunicorn app:app --bind 0.0.0.0:$PORT`
- Variáveis de ambiente obrigatórias: `DATABASE_URL`, `SECRET_KEY`, `TEACHER_PASSWORD_HASH`.
- Ative `COOKIE_SECURE=true` em HTTPS.
- Nunca publique segredos no GitHub, não compartilhe o hash da senha e faça backups do banco.

## Banco de dados

Tabelas criadas automaticamente pelo SQLAlchemy:

- `student`: matrícula única, nome, curso.
- `submission`: tentativa, framework, número do exercício, tipo do menu, código submetido, sucesso e feedback.
- `award`: aprovação única por aluno/framework/exercício, prevenindo pontos duplicados.

## Limitações importantes

- **Os dados ainda não estão salvos em um PostgreSQL hospedado por você**: é necessário configurar credenciais, criar as tabelas e publicar o servidor.
- A matrícula + nome + curso apenas identifica o aluno; **não é autenticação forte**. Para avaliação oficial, recomendam-se senha individual, login institucional ou SSO.
- A validação confere critérios sintáticos/estruturais; não garante acessibilidade, segurança ou qualidade visual. Um exercício não deve ser considerado prova de autoria apenas pela detecção de cópia literal.
- O verificador de cópia compara com o exemplo distribuído; soluções ligeiramente modificadas podem exigir revisão docente.
- O conteúdo digitado é executado no navegador em iframe sandbox; ainda assim, implantações públicas devem acrescentar limite de requisições, CSRF e política de segurança de conteúdo (CSP).
- Os dados de nome e matrícula são dados pessoais; avalie política de retenção, acesso, base legal e informações aos alunos antes do uso em turma real.
