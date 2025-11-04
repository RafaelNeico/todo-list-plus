import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import logging

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

# Configuração do banco de dados
def get_db_connection():
    """Estabelece conexão com o banco de dados"""
    try:
        # No Render, usa DATABASE_URL do environment
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL não encontrada")
            return None
            
        # Ajusta a string de conexão se necessário
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        logger.error(f"Erro ao conectar com o banco: {e}")
        return None

def init_db():
    """Inicializa o banco de dados criando a tabela se não existir"""
    conn = get_db_connection()
    if conn is None:
        return False
        
    try:
        with conn.cursor() as cur:
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(200) NOT NULL,
                    descricao TEXT,
                    concluida BOOLEAN DEFAULT FALSE,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            conn.commit()
            logger.info("Tabela 'tarefas' verificada/criada com sucesso")
            return True
    except Exception as e:
        logger.error(f"Erro ao criar tabela: {e}")
        return False
    finally:
        conn.close()

@app.route('/')
def index():
    """Página principal - Lista todas as tarefas"""
    conn = get_db_connection()
    if conn is None:
        return render_template('error.html', message="Erro de conexão com o banco de dados")
    
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM tarefas ORDER BY data_criacao DESC')
            tarefas = cur.fetchall()
            
        # Converter para lista de dicionários
        tarefas_list = []
        for tarefa in tarefas:
            tarefas_list.append({
                'id': tarefa[0],
                'titulo': tarefa[1],
                'descricao': tarefa[2],
                'concluida': tarefa[3],
                'data_criacao': tarefa[4]
            })
            
        return render_template('index.html', tarefas=tarefas_list)
        
    except Exception as e:
        logger.error(f"Erro ao buscar tarefas: {e}")
        return render_template('error.html', message="Erro ao carregar tarefas")
    finally:
        conn.close()

@app.route('/adicionar', methods=['POST'])
def adicionar_tarefa():
    """Adiciona uma nova tarefa"""
    titulo = request.form.get('titulo', '').strip()
    descricao = request.form.get('descricao', '').strip()
    
    if not titulo:
        return redirect(url_for('index'))
    
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                'INSERT INTO tarefas (titulo, descricao) VALUES (%s, %s)',
                (titulo, descricao)
            )
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao adicionar tarefa: {e}")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/concluir/<int:tarefa_id>')
def concluir_tarefa(tarefa_id):
    """Marca uma tarefa como concluída"""
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))
    
    try:
        with conn.cursor() as cur:
            cur.execute(
                'UPDATE tarefas SET concluida = TRUE WHERE id = %s',
                (tarefa_id,)
            )
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao concluir tarefa: {e}")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/excluir/<int:tarefa_id>')
def excluir_tarefa(tarefa_id):
    """Exclui uma tarefa"""
    conn = get_db_connection()
    if conn is None:
        return redirect(url_for('index'))
    
    try:
        with conn.cursor() as cur:
            cur.execute('DELETE FROM tarefas WHERE id = %s', (tarefa_id,))
            conn.commit()
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao excluir tarefa: {e}")
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/api/tarefas', methods=['GET'])
def api_tarefas():
    """API para listar tarefas (JSON)"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({'error': 'Database connection failed'}), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT * FROM tarefas ORDER BY data_criacao DESC')
            tarefas = cur.fetchall()
            
        tarefas_list = []
        for tarefa in tarefas:
            tarefas_list.append({
                'id': tarefa[0],
                'titulo': tarefa[1],
                'descricao': tarefa[2],
                'concluida': tarefa[3],
                'data_criacao': tarefa[4].isoformat() if tarefa[4] else None
            })
            
        return jsonify(tarefas_list)
        
    except Exception as e:
        logger.error(f"Erro na API: {e}")
        return jsonify({'error': str(e)}), 500
    finally:
        conn.close()

@app.route('/health')
def health_check():
    """Endpoint de health check para o Render"""
    conn = get_db_connection()
    db_status = "healthy" if conn else "unhealthy"
    if conn:
        conn.close()
    
    return jsonify({
        'status': 'healthy',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    })

# Inicialização do app
if __name__ == '__main__':
    # Tentar inicializar o banco
    if init_db():
        logger.info("Banco de dados inicializado com sucesso")
    else:
        logger.warning("Falha ao inicializar banco de dados")
    
    # Configurações para produção
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('DEBUG', 'False').lower() == 'true'
    
    app.run(host='0.0.0.0', port=port, debug=debug)