from flask import Flask, render_template, request, redirect, url_for, session
from werkzeug.security import generate_password_hash, check_password_hash
import mysql.connector 
from datetime import date 

# Aqui estamos criando o aplicativo de fato. A variável app é o coração do site.
app = Flask(__name__) 
app.secret_key = 'chave_secreta_tcc' # ESSENCIAL: A senha mestre para as sessões funcionarem

# ========================================================
# Filtro Personalizado do Jinja2 para Padrão Brasileiro
# ========================================================
@app.template_filter('moeda')
def format_moeda(valor):
    if valor is None:
        valor = 0.0
    # 1. Formata com 2 casas decimais e vírgula nos milhares (Padrão EUA: 1,500.00)
    valor_formatado = f"{float(valor):,.2f}"
    # 2. Truque de inversão: Troca vírgula por X, ponto por vírgula, e X por ponto
    return valor_formatado.replace(',', 'X').replace('.', ',').replace('X', '.')

# Configuração da fechadura do banco de dados
def conectar_banco():
    conexao = mysql.connector.connect(
        host = "localhost",
        user = "root",
        password = "root",
        database = "rota_financeira_db"
    )
    return conexao


# Rota da página inicial
@app.route('/')
def index():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))
        
    usuario_id = session['usuario_id']

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)

        # 1. Transações do usuário logado
        sql = "SELECT * FROM transacoes WHERE usuario_id = %s ORDER BY data_transacao DESC"
        cursor.execute(sql, (usuario_id,))
        minhas_transacoes = cursor.fetchall()
        
        # Motor matemático (mantém o loop exatamente igual)
        total_receitas = 0.0
        total_despesas = 0.0
        for transacao in minhas_transacoes:
            if transacao['tipo'] == 'receita':
                total_receitas += float(transacao['valor'])
            elif transacao['tipo'] == 'despesa':
                total_despesas += float(transacao['valor'])
                
        saldo_atual = total_receitas - total_despesas

        # 2. Metas do usuário logado
        sql_metas = "SELECT * FROM metas WHERE usuario_id = %s ORDER BY data_limite ASC"
        cursor.execute(sql_metas, (usuario_id,))
        minhas_metas = cursor.fetchall()

        for meta in minhas_metas:
            if float(meta['valor_alvo']) > 0:
                porcentagem = (float(meta['valor_atual']) / float(meta['valor_alvo'])) * 100
                meta['porcentagem'] = round(porcentagem, 1)
            else:
                meta['porcentagem'] = 0

        # 3. Gráfico do usuário logado
        lista_receitas_meses = [0.0] * 12
        lista_despesas_meses = [0.0] * 12

        sql_receitas_grafico = """
            SELECT MONTH(data_transacao) AS mes, SUM(valor) AS total 
            FROM transacoes 
            WHERE tipo = 'receita' AND usuario_id = %s 
            GROUP BY MONTH(data_transacao)
        """
        cursor.execute(sql_receitas_grafico, (usuario_id,))
        for linha in cursor.fetchall():
            lista_receitas_meses[linha['mes'] - 1] = float(linha['total'])

        sql_despesas_grafico = """
            SELECT MONTH(data_transacao) AS mes, SUM(valor) AS total 
            FROM transacoes 
            WHERE tipo = 'despesa' AND usuario_id = %s 
            GROUP BY MONTH(data_transacao)
        """
        cursor.execute(sql_despesas_grafico, (usuario_id,))
        for linha in cursor.fetchall():
            lista_despesas_meses[linha['mes'] - 1] = float(linha['total'])

        cursor.close()
        conexao.close()

    except Exception as e:
        print(f"Erro no banco: {e}")
        # (Manter o bloco de fallback do except)

    

    except Exception as e:
        # Trava para o pc: se não achar o banco, avisa no terminal e zera tudo
        print(f"Aviso: Banco não conectado. Carregando site vazio. Error: {e}")
        minhas_transacoes = []
        lista_receitas_meses = []
        lista_despesas_meses = []
        total_receitas = 0.0
        total_despesas = 0.0
        saldo_atual = 0.0
        minhas_metas = [] # <-- A variável de segurança adicionada!

    # Carrega o HTML e INJETA a lista de dados e as novas variáveis matemáticas!
    return render_template('index.html', 
                           lista_para_html=minhas_transacoes,
                           receitas_html=total_receitas,
                           despesas_html=total_despesas,
                           saldo_html=saldo_atual,
                           lista_metas=minhas_metas,
                           receitas_grafico=lista_receitas_meses,
                           despesas_grafico=lista_despesas_meses)

# Rota para testar o banco de dados
@app.route('/testar-banco')
def testar_banco():
    try:
        # Tenta abrir a conexão e fechar logo em seguida
        conexao = conectar_banco()
        conexao.close()
        return "<h1>Conexão com banco de dados feita com sucesso</h1>"
    except Exception as e:
        return f"<h1>Erro ao tentar conectar banco: {e}</h1>"

# Rota para receber os dados do usuario
@app.route('/adicionar-transacao', methods=['POST'])
def adicionar_transacao():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    descricao = request.form.get('descricao')
    valor = request.form.get('valor')  
    tipo = request.form.get('tipo')
    data_atual = date.today()
    usuario_id = session['usuario_id'] # Pega o ID do usuário conectado

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        sql = "INSERT INTO transacoes (usuario_id, descricao, valor, tipo, data_transacao) VALUES (%s, %s, %s, %s, %s)"
        valores = (usuario_id, descricao, valor, tipo, data_atual) # Substituído o 1 por usuario_id
        
        cursor.execute(sql, valores)
        conexao.commit()
        cursor.close()
        conexao.close()
        return redirect(url_for('index'))
    except Exception as e:
        return f"<h1>Erro ao salvar transação: {e}</h1>"


@app.route('/adicionar-meta', methods=['POST'])
def adicionar_meta():
    if 'usuario_id' not in session:
        return redirect(url_for('login'))

    nome_meta = request.form.get('nome_meta')
    valor_alvo = request.form.get('valor_alvo')
    data_limite = request.form.get('data_limite')
    usuario_id = session['usuario_id'] # Pega o ID do usuário conectado

    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        sql = "INSERT INTO metas (usuario_id, nome_meta, valor_alvo, data_limite) VALUES (%s, %s, %s, %s)"
        valores = (usuario_id, nome_meta, valor_alvo, data_limite) # Substituído o 1 por usuario_id
        
        cursor.execute(sql, valores)
        conexao.commit()
        cursor.close()
        conexao.close()
        return redirect(url_for('index'))
    except Exception as e:
        return f"<h1>Erro ao salvar meta: {e}</h1>"

# ========================================================
# INÍCIO DA SUPER META: Rotas de Autenticação (Telas)
# ========================================================
@app.route('/login')
def login():
    return render_template('login.html')

@app.route('/fazer-cadastro', methods=['POST'])
def fazer_cadastro():
    nome = request.form.get('nome')
    email = request.form.get('email')
    senha = request.form.get('senha')
    
    # Embaralhando a senha
    senha_criptografada = generate_password_hash(senha)
    
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor()
        
        # Inserindo no banco a senha embaralhada, e não a original
        sql = "INSERT INTO usuarios (nome, email, senha) VALUES (%s, %s, %s)"
        valores = (nome, email, senha_criptografada)
        
        cursor.execute(sql, valores)
        conexao.commit()
        
        cursor.close()
        conexao.close()
        
        print(f"NOVO USUÁRIO CADASTRADO: {nome} | Email: {email}")
        # Após cadastrar, joga o usuário para a tela de login
        return redirect(url_for('login')) 
        
    except Exception as e:
        return f"<h1>Erro ao tentar cadastrar usuário: {e}</h1>"

@app.route('/cadastro')
def cadastro():
    return render_template('cadastro.html')
# ========================================================
@app.route('/fazer-login', methods=['POST'])
def fazer_login():
    email_digitado = request.form.get('email')
    senha_digitada = request.form.get('senha')
    
    try:
        conexao = conectar_banco()
        cursor = conexao.cursor(dictionary=True)
        
        # 1. Busca no banco se existe alguém com esse e-mail
        sql = "SELECT * FROM usuarios WHERE email = %s"
        cursor.execute(sql, (email_digitado,))
        usuario = cursor.fetchone()
        
        cursor.close()
        conexao.close()
        
        # 2. Se o usuário existir, compara a senha digitada com o Hash do banco
        if usuario and check_password_hash(usuario['senha'], senha_digitada):
            
            # 3. A MÁGICA: Cria o "crachá" do usuário logado!
            session['usuario_id'] = usuario['id']
            session['usuario_nome'] = usuario['nome']
            
            print(f"LOGIN EFETUADO COM SUCESSO: {usuario['nome']}")
            # Devolve o usuário para o Dashboard
            return redirect(url_for('index'))
        else:
            return "<h1>E-mail ou senha incorretos! Volte e tente novamente.</h1>"
            
    except Exception as e:
        return f"<h1>Erro ao tentar fazer login: {e}</h1>"

@app.route('/logout')
def logout():
    session.clear() # Destroi todas as variáveis da sessão (o crachá)
    return redirect(url_for('login'))
    
    
# Trava de segurança - DEVE SER SEMPRE A ÚLTIMA COISA DO ARQUIVO!
if __name__ == '__main__':
    app.run(debug=True)