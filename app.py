import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for
import requests
from datetime import datetime
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

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
        logger.info("✅ Conectado ao PostgreSQL")
        return conn
    except Exception as e:
        logger.error(f"❌ Erro ao conectar com o banco: {e}")
        return None

def init_db():
    """Inicializa o banco de dados com tabela completa"""
    conn = get_db_connection()
    if conn is None:
        logger.error("Não foi possível conectar ao banco para inicialização")
        return False
        
    try:
        with conn.cursor() as cur:
            # PostgreSQL - criar tabela se não existir
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    descricao TEXT NOT NULL,
                    categoria TEXT DEFAULT 'Geral',
                    prioridade TEXT DEFAULT 'Média',
                    prazo TEXT,
                    concluida BOOLEAN DEFAULT FALSE,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("✅ Tabela PostgreSQL criada/verificada")
            return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela: {e}")
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()

def obter_clima(cidade='São Paulo'):
    """Obtém dados do clima da API OpenWeather"""
    try:
        api_key = os.environ.get('OPENWEATHER_API_KEY', '00242a4366f2f684e8f901da0d365d44')
        if not api_key or api_key == '00242a4366f2f684e8f901da0d365d44':
            return None
            
        url = f"http://api.openweathermap.org/data/2.5/weather?q={cidade}&appid={api_key}&units=metric&lang=pt_br"
        response = requests.get(url, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'cidade': data['name'],
                'temperatura': round(data['main']['temp']),
                'descricao': data['weather'][0]['description'].title(),
                'icone': data['weather'][0]['icon'],
                'sensacao': round(data['main']['feels_like']),
                'humidade': data['main']['humidity'],
                'vento': round(data['wind']['speed'] * 3.6)  # m/s para km/h
            }
        return None
    except Exception as e:
        logger.error(f"Erro ao obter clima: {e}")
        return None

# Rota principal com todas as funcionalidades
@app.route('/')
def index():
    try:
        filter_type = request.args.get('filter', 'all')
        
        conn = get_db_connection()
        if conn is None:
            return render_template('index.html', 
                                 tarefas=[], 
                                 clima=None,
                                 total=0, concluidas=0, pendentes=0,
                                 filter_type=filter_type,
                                 error="Erro de conexão com o banco de dados")
        
        with conn.cursor() as cur:
            # Aplicar filtros
            if filter_type == 'active':
                cur.execute('SELECT * FROM tarefas WHERE concluida = FALSE ORDER BY id DESC')
            elif filter_type == 'completed':
                cur.execute('SELECT * FROM tarefas WHERE concluida = TRUE ORDER BY id DESC')
            else:
                cur.execute('SELECT * FROM tarefas ORDER BY id DESC')
            
            tarefas_data = cur.fetchall()
        
        # Converter para formato padrão - CORREÇÃO AQUI
        tarefas = []
        for tarefa in tarefas_data:
            # PostgreSQL retorna 7 campos: id, descricao, categoria, prioridade, prazo, concluida, data_criacao
            tarefas.append({
                'id': tarefa[0],
                'descricao': tarefa[1],
                'categoria': tarefa[2],
                'prioridade': tarefa[3],
                'prazo': tarefa[4],
                'concluida': tarefa[5],
                'data_criacao': tarefa[6] if tarefa[6] else None
            })
        
        # Estatísticas
        total = len(tarefas)
        concluidas = len([t for t in tarefas if t['concluida']])
        pendentes = total - concluidas
        
        # Dados do clima
        clima = obter_clima()
        
        return render_template('index.html', 
                             tarefas=tarefas,
                             clima=clima,
                             total=total,
                             concluidas=concluidas,
                             pendentes=pendentes,
                             filter_type=filter_type)
    
    except Exception as e:
        logger.error(f"Erro na rota principal: {e}")
        return render_template('index.html', 
                             tarefas=[], 
                             clima=None,
                             total=0, concluidas=0, pendentes=0,
                             filter_type='all',
                             error=f"Erro interno: {str(e)}")

# Rotas CRUD completas
@app.route('/add', methods=['POST'])
def add_task():
    try:
        descricao = request.form['descricao']
        categoria = request.form.get('categoria', 'Geral')
        prioridade = request.form.get('prioridade', 'Média')
        prazo = request.form.get('prazo', '')
        
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))
        
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO tarefas (descricao, categoria, prioridade, prazo) VALUES (%s, %s, %s, %s)',
                (descricao, categoria, prioridade, prazo)
            )
            conn.commit()
        
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao adicionar tarefa: {e}")
        return redirect(url_for('index'))

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    try:
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))
        
        with conn.cursor() as cur:
            cur.execute('UPDATE tarefas SET concluida = TRUE WHERE id = %s', (task_id,))
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao concluir tarefa: {e}")
        return redirect(url_for('index'))

@app.route('/reopen/<int:task_id>')
def reopen_task(task_id):
    try:
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))
        
        with conn.cursor() as cur:
            cur.execute('UPDATE tarefas SET concluida = FALSE WHERE id = %s', (task_id,))
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao reabrir tarefa: {e}")
        return redirect(url_for('index'))

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    try:
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))
        
        with conn.cursor() as cur:
            cur.execute('DELETE FROM tarefas WHERE id = %s', (task_id,))
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao excluir tarefa: {e}")
        return redirect(url_for('index'))

@app.route('/clear_completed')
def clear_completed():
    try:
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))
        
        with conn.cursor() as cur:
            cur.execute('DELETE FROM tarefas WHERE concluida = TRUE')
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao limpar concluídas: {e}")
        return redirect(url_for('index'))

# Rota de saúde melhorada para o Fly.io
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

# Adicione esta importação no topo se não existir
from flask import jsonify

# Inicialização
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Quando rodando com Gunicorn
    init_db()