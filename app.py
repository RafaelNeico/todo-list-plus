import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime
import logging
import urllib.parse

# Configuração de logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

def get_db_connection():
    """Conecta ao PostgreSQL do Render"""
    try:
        # No Render, a DATABASE_URL é fornecida automaticamente
        database_url = os.environ.get('DATABASE_URL')
        
        if not database_url:
            logger.error("DATABASE_URL não encontrada")
            return None
        
        # Parse da URL para garantir compatibilidade
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
        logger.error("Não foi possível conectar ao banco para inicialização")
        return False
        
    try:
        with conn.cursor() as cur:
            # Criar tabela de tarefas
            cur.execute('''
                CREATE TABLE IF NOT EXISTS tarefas (
                    id SERIAL PRIMARY KEY,
                    titulo VARCHAR(200) NOT NULL,
                    descricao TEXT,
                    concluida BOOLEAN DEFAULT FALSE,
                    data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Criar índice para melhor performance
            cur.execute('''
                CREATE INDEX IF NOT EXISTS idx_tarefas_data 
                ON tarefas(data_criacao DESC)
            ''')
            
            conn.commit()
            logger.info("✅ Tabela 'tarefas' criada/verificada com sucesso")
            return True
    except Exception as e:
        logger.error(f"❌ Erro ao criar tabela: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

@app.route('/')
def index():
    """Página principal - Lista todas as tarefas"""
    conn = get_db_connection()
    if conn is None:
        return render_template('index.html', 
                             tarefas=[], 
                             error="Erro de conexão com o banco de dados")
    
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT id, titulo, descricao, concluida, 
                       TO_CHAR(data_criacao, 'DD/MM/YYYY HH24:MI') as data_formatada
                FROM tarefas 
                ORDER BY data_criacao DESC
            ''')
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
        return render_template('index.html', 
                             tarefas=[], 
                             error="Erro ao carregar tarefas")
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
            logger.info(f"Tarefa adicionada: {titulo}")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao adicionar tarefa: {e}")
        conn.rollback()
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
            logger.info(f"Tarefa {tarefa_id} marcada como concluída")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao concluir tarefa: {e}")
        conn.rollback()
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
            logger.info(f"Tarefa {tarefa_id} excluída")
        return redirect(url_for('index'))
    except Exception as e:
        logger.error(f"Erro ao excluir tarefa: {e}")
        conn.rollback()
        return redirect(url_for('index'))
    finally:
        conn.close()

@app.route('/editar/<int:tarefa_id>', methods=['GET', 'POST'])
def editar_tarefa(tarefa_id):
    """Edita uma tarefa existente"""
    if request.method == 'GET':
        # Mostrar formulário de edição
        conn = get_db_connection()
        if conn is None:
            return redirect(url_for('index'))
        
        try:
            with conn.cursor() as cur:
                cur.execute('SELECT * FROM tarefas WHERE id = %s', (tarefa_id,))
                tarefa = cur.fetchone()
                
            if tarefa:
                tarefa_dict = {
                    'id': tarefa[0],
                    'titulo': tarefa[1],
                    'descricao': tarefa[2],
                    'concluida': tarefa[3]
                }
                return render_template('editar.html', tarefa=tarefa_dict)
            else:
                return redirect(url_for('index'))
                
        except Exception as e:
            logger.error(f"Erro ao carregar tarefa para edição: {e}")
            return redirect(url_for('index'))
        finally:
            conn.close()
    
    else:
        # Processar edição
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
                    'UPDATE tarefas SET titulo = %s, descricao = %s WHERE id = %s',
                    (titulo, descricao, tarefa_id)
                )
                conn.commit()
                logger.info(f"Tarefa {tarefa_id} editada")
            return redirect(url_for('index'))
        except Exception as e:
            logger.error(f"Erro ao editar tarefa: {e}")
            conn.rollback()
            return redirect(url_for('index'))
        finally:
            conn.close()

@app.route('/health')
def health_check():
    """Health check para monitoramento"""
    conn = get_db_connection()
    if conn is None:
        return jsonify({
            'status': 'error',
            'database': 'disconnected',
            'timestamp': datetime.now().isoformat()
        }), 500
    
    try:
        with conn.cursor() as cur:
            cur.execute('SELECT COUNT(*) as count FROM tarefas')
            count = cur.fetchone()[0]
            
            cur.execute('SELECT MAX(data_criacao) as ultima FROM tarefas')
            ultima_tarefa = cur.fetchone()[0]
            
        return jsonify({
            'status': 'healthy',
            'database': 'connected',
            'tarefas_count': count,
            'ultima_tarefa': ultima_tarefa.isoformat() if ultima_tarefa else None,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500
    finally:
        conn.close()

@app.route('/api/tarefas')
def api_tarefas():
    """API para outras aplicações"""
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

# Inicialização
if __name__ == '__main__':
    if init_db():
        logger.info("✅ Aplicação inicializada com sucesso")
    else:
        logger.error("❌ Falha na inicialização do banco de dados")
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Quando rodando com Gunicorn
    init_db()