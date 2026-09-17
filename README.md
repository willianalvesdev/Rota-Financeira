# Rota Financeira

Aplicação de finanças pessoais em português, com Flask e MySQL. Inclui contas individuais, receitas e despesas, resumo mensal, saldo acumulado, gráfico anual e metas com aportes. Interface responsiva com temas claro e escuro, CSS próprio e recursos locais: não depende de Bootstrap, Chart.js ou CDNs.

Identidade visual: logos e favicon fornecidos, Poppins local e paleta base `#0C0C0C`, `#232323`, `#49494B`, `#B3B3B3`, `#FFFFFF`. Receitas e aumentos usam `#4BD964`; despesas e perdas usam `#FF443A`, acompanhados de rótulos, sinais e ícones. Não utiliza sombras. O único gradiente fica no preenchimento do gráfico de linhas, que também pode ser exibido em barras. O tema inicial é escuro.

## Executar neste computador

O ambiente `venv`, o arquivo `.env` e o MySQL local foram configurados durante a revisão. Abra **iniciar.bat** ou execute, na pasta do projeto:

```powershell
.\venv\Scripts\python.exe run.py
```

Acesse **http://127.0.0.1:5000** e crie sua conta. Não há conta padrão ou dados fictícios no banco da aplicação. Mantenha o terminal aberto enquanto usa o site. Encerre com `Ctrl+C`. Se a porta 5000 já estiver ocupada, use a instância em execução ou altere `APP_PORT` no `.env`.

## Instalar em outro computador

Requisitos: Python 3.13 e MySQL 8.0.16 ou superior (com serviço iniciado). Os comandos abaixo são para PowerShell, na pasta do projeto.

```powershell
py -3.13 -m venv venv
.\venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
.\venv\Scripts\python.exe -c "import secrets; print(secrets.token_hex(32))"
```

Copie a chave gerada para `SECRET_KEY` no `.env`. Gere outra chave para `DB_PASSWORD`. Mantenha `DB_USER=rota_financeira_app` ou escolha outro nome exclusivo, diferente do administrador. O `.env` real é ignorado pelo Git e contém segredos: não o compartilhe.

Prepare o banco e o usuário da aplicação:

```powershell
.\venv\Scripts\python.exe scripts\configurar_banco.py --admin-user root
.\venv\Scripts\python.exe run.py
```

O configurador pede a senha administrativa do MySQL, cria estruturas ausentes e concede `SELECT`, `INSERT`, `UPDATE` e `DELETE` ao usuário da aplicação, somente neste banco. Não apaga registros e não muda a senha de uma conta MySQL já existente. Se essa conta já existir, o `.env` deve usar sua senha correta. A migração desta versão acrescenta o marcador de reserva inicial e permite valor e prazo vazios somente na reserva ainda não configurada. Antes de aplicar mudanças a um banco existente em outra instalação, faça backup e revise sua estrutura.

O arquivo `setup_banco_sq.sql` também pode ser aberto no MySQL Workbench para criar o banco e as tabelas. Ele não cria o usuário da aplicação. Para apenas verificar/criar as tabelas pela aplicação:

```powershell
.\venv\Scripts\python.exe -m flask --app run init-db --admin-user root
```

## Regras dos dados

- Receitas e despesas do resumo pertencem ao **mês selecionado**. O saldo acumulado considera todo o histórico do usuário.
- O gráfico compara os 12 meses do **ano selecionado**. Filtros por descrição/tipo e paginação afetam a lista, sem alterar os totais do período.
- A comparação anual usa o acumulado até o fim do mês selecionado, limitado a hoje no ano corrente, contra o mesmo período do ano anterior. Em anos bissextos, o corte anterior é ajustado para a última data válida. Quando a base é zero, não se inventa uma porcentagem.
- Cada conta recebe uma única **Reserva de emergência**, sem valor ou prazo inventados. Configure-a antes de adicionar aportes. Se você a excluir, ela não reaparece automaticamente. A migração também atende contas anteriores sem duplicar uma reserva com esse nome.
- Valores usam `Decimal` no Python e `DECIMAL(12,2)` no banco. Entradas aceitam até duas casas decimais; transações e aportes precisam ser positivos. O máximo por valor é R$ 9.999.999.999,99.
- As transações são realizadas: sua data não pode estar no futuro. Novas metas precisam ter prazo a partir de hoje. Metas existentes podem manter um prazo vencido.
- Aportes aumentam somente o valor guardado na meta. **Não movimentam dinheiro nem alteram transações ou saldo.** Uma meta pode ultrapassar o alvo; o indicador visual para em 100%.
- E-mails são normalizados e únicos. Senhas têm 8–128 caracteres e são armazenadas como hashes scrypt, nunca em texto puro.
- Alterações e exclusões exigem autenticação, validação CSRF e propriedade do registro. Exclusões de transações/metas são definitivas após confirmação.
- Sessões expiram em oito horas e são revogadas no servidor ao sair. Uma cópia antiga do cookie não restaura uma sessão encerrada.

## Organização

```text
run.py                      Entrada do servidor Waitress
rota_financeira/
  __init__.py               Configuração, segurança e erros
  db.py                     Conexões e inicialização do MySQL
  defaults.py               Reserva inicial idempotente
  public.py                 Privacidade, contato e metadados públicos
  views.py                  Autenticação, painel e operações
  validation.py             Valores, datas e formatação
templates/                  Páginas e componentes Jinja
static/css/style.css        Tokens de temas e todos os estilos
static/js/app.js            Temas, diálogos e gráfico SVG
scripts/configurar_banco.py  Preparação local do banco
setup_banco_sq.sql          Schema completo
tests/                      Testes de integração com MySQL isolado
```

Personalize os tokens de cores, fontes, espaçamentos e raios no `:root` de `static/css/style.css`. As substituições do tema escuro ficam em `[data-theme="dark"]`. Os cantos usam `corner-shape: squircle` nos navegadores compatíveis, com arredondamento convencional como fallback. Os gráficos também têm uma tabela acessível com os valores mensais. A fonte Poppins está em `static/fonts`, com sua licença SIL Open Font License em `OFL.txt`, obtida do repositório oficial [Google Fonts](https://github.com/google/fonts/tree/main/ofl/poppins). As logos estão em `static/img`.

## Preferências, páginas públicas e ícone

O diálogo de cookies permite escolher somente os essenciais ou autorizar preferências. Tema, menu recolhido e formato do gráfico só são salvos quando permitidos. A decisão fica no armazenamento local por seis meses e pode ser alterada pelo rodapé. Não há publicidade nem ferramentas externas de análise de visitas.

O rodapé aponta para `/privacidade` e `/contato`. Os canais de contato e redes sociais ficam explicitamente pendentes até o responsável informar os links reais; o contexto aceita as configurações `CONTACT_EMAIL` e `SOCIAL_LINKS` (lista de objetos com `nome` e `url`). Revise a política para refletir o operador e a hospedagem usados antes de publicar.

O manifest e o ícone Apple permitem usar a identidade visual quando alguém adiciona o site à tela inicial pelo próprio navegador. Não há convites de instalação, página de instalação, service worker nem modo offline. Para acessar pelo celular, o site precisa de um endereço alcançável nesse aparelho; `127.0.0.1` refere-se ao próprio dispositivo. Use HTTPS na hospedagem.

`robots.txt` desencoraja o acesso de robôs às áreas privadas; `llms.txt` descreve apenas recursos públicos. Ambos são orientações para robôs, não controles de segurança: a proteção dos dados depende da autenticação e das verificações de propriedade no servidor.

## Verificação

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\venv\Scripts\python.exe -m pytest -q
.\venv\Scripts\python.exe -m ruff check .
.\venv\Scripts\python.exe -m pip check
```

Os testes usam um banco descartável `rota_financeira_test_<identificador-aleatorio>`, criado e removido pela própria suíte. Não apontam para o banco real. Configure `MYSQL_TEST_HOST`, `MYSQL_TEST_PORT`, `MYSQL_TEST_USER` e `MYSQL_TEST_PASSWORD` conforme sua instalação. O usuário de testes precisa poder criar e remover esse banco isolado. Os valores padrão atendem apenas ao ambiente local desta revisão (`127.0.0.1:3306`, usuário e senha `root`). A aplicação normal usa sua conta limitada, independentemente disso.

São verificados autenticação, senhas, CSRF, isolamento entre contas, valores inválidos, precisão de centavos, meses/anos, filtros, paginação, edição/exclusão, aportes concorrentes, falhas do banco e limites de tentativas de login.

## Publicação e manutenção

O servidor inicia apenas em `127.0.0.1`, sem debugger. Para publicar na internet, configure uma hospedagem com HTTPS, defina `SESSION_COOKIE_SECURE=true`, mantenha os segredos fora do repositório e estabeleça backups regulares do MySQL. A limitação de tentativas usa memória por processo nesta instalação; para várias instâncias, configure `RATELIMIT_STORAGE_URI` com um armazenamento compartilhado, como Redis, e instale o suporte correspondente de `limits`. Revise cabeçalhos de proxy antes de expor o serviço; a aplicação não confia automaticamente em `X-Forwarded-For`.

O projeto não inclui recuperação de senha por e-mail nem integrações bancárias. A conferência local não substitui monitoramento, backups e uma revisão de segurança do ambiente de produção.
