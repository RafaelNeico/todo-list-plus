import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, jsonify, make_response
import requests
from datetime import datetime
import logging
import uuid

# Configuração de logging mais detalhada
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'dev-key-please-change-in-production')

# Configuração do Banco - Fly.io com PostgreSQL
def get_db_connection():
    try:
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL não encontrada")
            return None
            
        # Ajusta a URL se necessário
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com o banco: {e}")
        return None

def init_db():
    """Inicializa o banco de dados - cria a tabela se não existir, SEM apagar dados"""
    logger.info("🔄 Verificando estrutura do banco de dados...")
    conn = get_db_connection()
    if conn is None:
        logger.error("Não foi possível conectar ao banco para inicialização")
        return False
        
    try:
        with conn.cursor() as cur:
            # Criar tabela apenas se não existir (NÃO usa DROP)
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    user_id TEXT NOT NULL,
                    descricao TEXT NOT NULL,
                    categoria TEXT DEFAULT 'Geral',
                    prioridade TEXT DEFAULT 'Média',
                    prazo TEXT,
                    concluida BOOLEAN DEFAULT FALSE,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Verificar se todas as colunas existem
            colunas_necessarias = ['user_id', 'categoria', 'prioridade', 'prazo']
            for coluna in colunas_necessarias:
                cur.execute("""
                    SELECT column_name 
                    FROM information_schema.columns 
                    WHERE table_name = 'tarefas' AND column_name = %s
                """, (coluna,))
                if not cur.fetchone():
                    logger.info(f"Adicionando coluna faltante: {coluna}")
                    if coluna == 'user_id':
                        cur.execute("ALTER TABLE tarefas ADD COLUMN user_id TEXT NOT NULL DEFAULT 'default'")
                    elif coluna == 'categoria':
                        cur.execute("ALTER TABLE tarefas ADD COLUMN categoria TEXT DEFAULT 'Geral'")
                    elif coluna == 'prioridade':
                        cur.execute("ALTER TABLE tarefas ADD COLUMN prioridade TEXT DEFAULT 'Média'")
                    elif coluna == 'prazo':
                        cur.execute("ALTER TABLE tarefas ADD COLUMN prazo TEXT")
            
            conn.commit()
            
            # Verificar quantas tarefas existem
            cur.execute("SELECT COUNT(*) FROM tarefas")
            count = cur.fetchone()[0]
            logger.info(f"✅ Estrutura do banco verificada. Tarefas totais: {count}")
            
            return True
            
    except Exception as e:
        logger.error(f"❌ Erro ao verificar estrutura do banco: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def get_user_id():
    """Obtém o user_id do cookie ou gera um novo"""
    user_id = request.cookies.get('user_id')
    if not user_id:
        user_id = str(uuid.uuid4())
        logger.info(f"🎉 Novo usuário criado: {user_id}")
    return user_id

def set_user_cookie(response, user_id):
    """Define o cookie do usuário"""
    response.set_cookie('user_id', user_id, max_age=60*60*24*365)  # 1 ano
    return response

def obter_clima(cidade='São Paulo'):
    """Obtém dados do clima da API OpenWeather - VERSÃO MELHORADA"""
    try:
        api_key = os.environ.get('OPENWEATHER_API_KEY')
        
        # Log para debug
        logger.info(f"🌤️ Tentando obter clima para {cidade}")
        
        if not api_key:
            logger.warning("⚠️ OPENWEATHER_API_KEY não encontrada nas variáveis de ambiente")
            return {
                'cidade': cidade,
                'temperatura': '--',
                'descricao': 'Dados indisponíveis',
                'icone': '01d',
                'sensacao': '--',
                'humidade': '--',
                'vento': '--',
                'erro': 'Chave da API não configurada'
            }
        
        # Verificar se é a chave padrão (que pode não funcionar)
        if api_key == '00242a4366f2f684e8f901da0d365d44':
            logger.warning("⚠️ Usando chave da API padrão - pode não funcionar")
        
        url = f"http://api.openweathermap.org/data/2.5/weather?q={cidade}&appid={api_key}&units=metric&lang=pt_br"
        logger.info(f"🌐 Chamando API do clima")
        
        response = requests.get(url, timeout=10)
        logger.info(f"📡 Status da resposta: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            clima_data = {
                'cidade': data['name'],
                'temperatura': round(data['main']['temp']),
                'descricao': data['weather'][0]['description'].title(),
                'icone': data['weather'][0]['icon'],
                'sensacao': round(data['main']['feels_like']),
                'humidade': data['main']['humidity'],
                'vento': round(data['wind']['speed'] * 3.6)  # Convertendo m/s para km/h
            }
            logger.info(f"✅ Clima obtido: {clima_data['temperatura']}°C em {clima_data['cidade']}")
            return clima_data
        else:
            logger.error(f"❌ Erro na API do clima: {response.status_code}")
            return {
                'cidade': cidade,
                'temperatura': '--',
                'descricao': 'Erro na API',
                'icone': '01d',
                'sensacao': '--',
                'humidade': '--',
                'vento': '--',
                'erro': f"HTTP {response.status_code}"
            }
            
    except requests.exceptions.Timeout:
        logger.error("⏰ Timeout ao obter dados do clima")
        return {
            'cidade': cidade,
            'temperatura': '--',
            'descricao': 'Timeout',
            'icone': '01d',
            'sensacao': '--',
            'humidade': '--',
            'vento': '--',
            'erro': 'Timeout'
        }
    except requests.exceptions.ConnectionError:
        logger.error("🔌 Erro de conexão ao obter dados do clima")
        return {
            'cidade': cidade,
            'temperatura': '--',
            'descricao': 'Sem conexão',
            'icone': '01d',
            'sensacao': '--',
            'humidade': '--',
            'vento': '--',
            'erro': 'Connection error'
        }
    except Exception as e:
        logger.error(f"❌ Erro inesperado ao obter clima: {e}")
        return {
            'cidade': cidade,
            'temperatura': '--',
            'descricao': 'Erro',
            'icone': '01d',
            'sensacao': '--',
            'humidade': '--',
            'vento': '--',
            'erro': str(e)
        }

# Rota principal - CORRIGIDA com mapeamento dinâmico
@app.route('/')
def index():
    try:
        filter_type = request.args.get('filter', 'all')
        user_id = get_user_id()
        
        logger.info(f"📱 Usuário {user_id[:8]} acessando a página com filtro: {filter_type}")
        
        conn = get_db_connection()
        if conn is None:
            logger.error("❌ Falha na conexão com o banco")
            response = make_response(render_template('index.html', 
                                 tarefas=[], 
                                 clima=None,
                                 total=0, concluidas=0, pendentes=0,
                                 filter_type=filter_type,
                                 error="Erro de conexão com o banco de dados",
                                 user_id=user_id))
            return set_user_cookie(response, user_id)
        
        with conn.cursor() as cur:
            # Aplicar filtros com user_id
            if filter_type == 'active':
                cur.execute('SELECT * FROM tarefas WHERE user_id = %s AND concluida = FALSE ORDER BY id DESC', (user_id,))
            elif filter_type == 'completed':
                cur.execute('SELECT * FROM tarefas WHERE user_id = %s AND concluida = TRUE ORDER BY id DESC', (user_id,))
            else:
                cur.execute('SELECT * FROM tarefas WHERE user_id = %s ORDER BY id DESC', (user_id,))
            
            tarefas_data = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]  # Obter nomes das colunas
            logger.info(f"📊 Encontradas {len(tarefas_data)} tarefas para o usuário {user_id[:8]}")
        
        # Converter usando mapeamento por nome de coluna - CORREÇÃO CRÍTICA
        tarefas = []
        for tarefa_row in tarefas_data:
            # Criar dicionário mapeando nome da coluna para valor
            tarefa_dict = {}
            for i, col_name in enumerate(col_names):
                tarefa_dict[col_name] = tarefa_row[i]
            
            # Formatar data_criacao
            data_criacao = tarefa_dict.get('data_criacao')
            data_formatada = None
            
            if data_criacao:
                if isinstance(data_criacao, str):
                    try:
                        data_obj = datetime.fromisoformat(data_criacao.replace('Z', '+00:00'))
                        data_formatada = data_obj.strftime('%d/%m/%Y %H:%M')
                    except (ValueError, AttributeError):
                        data_formatada = data_criacao
                else:
                    data_formatada = data_criacao.strftime('%d/%m/%Y %H:%M')
            
            # Mapeamento CORRETO dos campos
            tarefa = {
                'id': tarefa_dict.get('id'),
                'descricao': tarefa_dict.get('descricao'),
                'categoria': tarefa_dict.get('categoria', 'Geral'),
                'prioridade': tarefa_dict.get('prioridade', 'Média'),
                'prazo': tarefa_dict.get('prazo'),
                'concluida': bool(tarefa_dict.get('concluida', False)),  # Garantir que é booleano
                'data_criacao': data_formatada
            }
            
            tarefas.append(tarefa)
        
        # Estatísticas
        total = len(tarefas)
        concluidas = len([t for t in tarefas if t['concluida']])
        pendentes = total - concluidas
        
        logger.info(f"📈 Estatísticas - Total: {total}, Concluídas: {concluidas}, Pendentes: {pendentes}")
        
        # Dados do clima
        clima = obter_clima()
        if clima and 'erro' in clima:
            logger.warning(f"⚠️ Clima com erro: {clima['erro']}")
        
        response = make_response(render_template('index.html', 
                             tarefas=tarefas,
                             clima=clima,
                             total=total,
                             concluidas=concluidas,
                             pendentes=pendentes,
                             filter_type=filter_type,
                             user_id=user_id))
        return set_user_cookie(response, user_id)
    
    except Exception as e:
        logger.error(f"❌ Erro na rota principal: {e}")
        user_id = get_user_id()
        response = make_response(render_template('index.html', 
                             tarefas=[], 
                             clima=None,
                             total=0, concluidas=0, pendentes=0,
                             filter_type='all',
                             error=f"Erro interno: {str(e)}",
                             user_id=user_id))
        return set_user_cookie(response, user_id)
    
@app.route('/add', methods=['POST'])
def add_task():
    try:
        descricao = request.form.get('descricao', '').strip()
        categoria = request.form.get('categoria', 'Geral')
        prioridade = request.form.get('prioridade', 'Média')
        prazo = request.form.get('prazo', '')
        user_id = get_user_id()
        
        logger.info(f"➕ Adicionando tarefa para user_id {user_id[:8]}: {descricao}")
        
        if not descricao:
            logger.warning("Tentativa de adicionar tarefa sem descrição")
            response = redirect(url_for('index'))
            return set_user_cookie(response, user_id)
        
        conn = get_db_connection()
        if conn is None:
            logger.error("❌ Falha na conexão com o banco ao adicionar tarefa")
            response = redirect(url_for('index'))
            return set_user_cookie(response, user_id)
        
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO tarefas (user_id, descricao, categoria, prioridade, prazo) VALUES (%s, %s, %s, %s, %s)',
                (user_id, descricao, categoria, prioridade, prazo)
            )
            conn.commit()
            logger.info(f"✅ Tarefa '{descricao}' adicionada com sucesso para user_id {user_id[:8]}!")
        
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)
        
    except Exception as e:
        logger.error(f"❌ Erro ao adicionar tarefa: {e}")
        user_id = get_user_id()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    try:
        user_id = get_user_id()
        logger.info(f"✅ Completando tarefa {task_id} para user_id {user_id[:8]}")
        
        conn = get_db_connection()
        if conn is None:
            response = redirect(url_for('index'))
            return set_user_cookie(response, user_id)
        
        with conn.cursor() as cur:
            cur.execute('UPDATE tarefas SET concluida = TRUE WHERE id = %s AND user_id = %s', (task_id, user_id))
            conn.commit()
            logger.info(f"🎯 Tarefa {task_id} marcada como concluída")
        
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)
    except Exception as e:
        logger.error(f"Erro ao concluir tarefa: {e}")
        user_id = get_user_id()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)

@app.route('/reopen/<int:task_id>')
def reopen_task(task_id):
    try:
        user_id = get_user_id()
        logger.info(f"🔄 Reabrindo tarefa {task_id} para user_id {user_id[:8]}")
        
        conn = get_db_connection()
        if conn is None:
            response = redirect(url_for('index'))
            return set_user_cookie(response, user_id)
        
        with conn.cursor() as cur:
            cur.execute('UPDATE tarefas SET concluida = FALSE WHERE id = %s AND user_id = %s', (task_id, user_id))
            conn.commit()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)
    except Exception as e:
        logger.error(f"Erro ao reabrir tarefa: {e}")
        user_id = get_user_id()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    try:
        user_id = get_user_id()
        logger.info(f"🗑️ Excluindo tarefa {task_id} para user_id {user_id[:8]}")
        
        conn = get_db_connection()
        if conn is None:
            response = redirect(url_for('index'))
            return set_user_cookie(response, user_id)
        
        with conn.cursor() as cur:
            cur.execute('DELETE FROM tarefas WHERE id = %s AND user_id = %s', (task_id, user_id))
            conn.commit()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)
    except Exception as e:
        logger.error(f"Erro ao excluir tarefa: {e}")
        user_id = get_user_id()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)

@app.route('/clear_completed')
def clear_completed():
    try:
        user_id = get_user_id()
        logger.info(f"🧹 Limpando tarefas concluídas para user_id {user_id[:8]}")
        
        conn = get_db_connection()
        if conn is None:
            response = redirect(url_for('index'))
            return set_user_cookie(response, user_id)
        
        with conn.cursor() as cur:
            cur.execute('DELETE FROM tarefas WHERE concluida = TRUE AND user_id = %s', (user_id,))
            conn.commit()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)
    except Exception as e:
        logger.error(f"Erro ao limpar concluídas: {e}")
        user_id = get_user_id()
        response = redirect(url_for('index'))
        return set_user_cookie(response, user_id)

@app.route('/debug-db')
def debug_db():
    """Página de diagnóstico do banco de dados - MELHORADA"""
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        return jsonify({'error': 'Não foi possível conectar ao banco'}), 500
    
    try:
        with conn.cursor() as cur:
            # Verificar estrutura detalhada da tabela
            cur.execute("""
                SELECT 
                    column_name, 
                    data_type, 
                    is_nullable,
                    column_default,
                    ordinal_position
                FROM information_schema.columns 
                WHERE table_name = 'tarefas'
                ORDER BY ordinal_position
            """)
            columns = cur.fetchall()
            
            # Verificar constraints e índices
            cur.execute("""
                SELECT 
                    conname, 
                    contype,
                    pg_get_constraintdef(oid) 
                FROM pg_constraint 
                WHERE conrelid = 'tarefas'::regclass
            """)
            constraints = cur.fetchall()
            
            # Contar tarefas do usuário
            cur.execute("SELECT COUNT(*) FROM tarefas WHERE user_id = %s", (user_id,))
            user_count = cur.fetchone()[0]
            
            # Contar tarefas totais
            cur.execute("SELECT COUNT(*) FROM tarefas")
            total_count = cur.fetchone()[0]
            
            # Contar tarefas concluídas vs pendentes
            cur.execute("SELECT COUNT(*) FROM tarefas WHERE user_id = %s AND concluida = TRUE", (user_id,))
            user_concluidas = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM tarefas WHERE user_id = %s AND concluida = FALSE", (user_id,))
            user_pendentes = cur.fetchone()[0]
            
            # Listar tarefas recentes do usuário COM TODOS OS CAMPOS
            cur.execute("SELECT * FROM tarefas WHERE user_id = %s ORDER BY id DESC LIMIT 10", (user_id,))
            recent_tasks = cur.fetchall()
            col_names = [desc[0] for desc in cur.description]  # Pegar nomes das colunas
            
        # Mostrar estrutura real das tarefas
        tasks_formatted = []
        for task in recent_tasks:
            task_dict = {}
            for i, col_name in enumerate(col_names):
                value = task[i]
                # Formatar datas
                if col_name == 'data_criacao' and value:
                    if isinstance(value, str):
                        try:
                            value = datetime.fromisoformat(value.replace('Z', '+00:00')).isoformat()
                        except (ValueError, AttributeError):
                            pass
                    else:
                        value = value.isoformat()
                task_dict[col_name] = value
            tasks_formatted.append(task_dict)
            
        response = jsonify({
            'user_id': user_id,
            'database_connected': True,
            'table_structure': {
                'columns': [{
                    'name': col[0], 
                    'type': col[1], 
                    'nullable': col[2],
                    'default': col[3],
                    'position': col[4]
                } for col in columns],
                'constraints': [{
                    'name': con[0],
                    'type': con[1],
                    'definition': con[2]
                } for con in constraints]
            },
            'statistics': {
                'user_tasks_count': user_count,
                'user_completed_tasks': user_concluidas,
                'user_pending_tasks': user_pendentes,
                'total_tasks_count': total_count
            },
            'recent_tasks_raw_structure': {
                'column_names': col_names,
                'tasks': tasks_formatted
            }
        })
        return set_user_cookie(response, user_id)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/meu-perfil')
def meu_perfil():
    user_id = get_user_id()
    conn = get_db_connection()
    if not conn:
        response = make_response(render_template('perfil.html', 
                              user_id=user_id,
                              tarefas_count=0,
                              error="Erro de conexão com o banco"))
        return set_user_cookie(response, user_id)
    
    try:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM tarefas WHERE user_id = %s", (user_id,))
            total = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM tarefas WHERE user_id = %s AND concluida = TRUE", (user_id,))
            concluidas = cur.fetchone()[0]
            
            cur.execute("SELECT COUNT(*) FROM tarefas WHERE user_id = %s AND concluida = FALSE", (user_id,))
            pendentes = cur.fetchone()[0]
        
        response = make_response(render_template('perfil.html',
                              user_id=user_id,
                              tarefas_count=total,
                              concluidas=concluidas,
                              pendentes=pendentes))
        return set_user_cookie(response, user_id)
    except Exception as e:
        response = make_response(render_template('perfil.html',
                              user_id=user_id,
                              tarefas_count=0,
                              error=str(e)))
        return set_user_cookie(response, user_id)

@app.route('/health')
def health():
    try:
        conn = get_db_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute('SELECT COUNT(*) FROM tarefas')
                count = cur.fetchone()[0]
            conn.close()
            return jsonify({
                'status': 'healthy',
                'database': 'connected',
                'tarefas_count': count,
                'timestamp': datetime.now().isoformat()
            }), 200
        else:
            return jsonify({
                'status': 'unhealthy',
                'database': 'disconnected',
                'timestamp': datetime.now().isoformat()
            }), 500
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

# Inicialização
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    logger.info("🚀 Iniciando aplicação com Gunicorn...")
    init_db()