import os
import psycopg2
from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime

app = Flask(__name__)

def get_db_connection():
    """Conecta ao banco de dados"""
    try:
        # Para Render - usa DATABASE_URL do environment
        database_url = os.environ.get('DATABASE_URL', '')
        
        # Corrige a URL se necessário
        if database_url.startswith("postgres://"):
            database_url = database_url.replace("postgres://", "postgresql://", 1)
            
        conn = psycopg2.connect(database_url)
        return conn
    except Exception as e:
        print(f"Erro de conexão: {e}")
        return None

def init_db():
    """Cria a tabela se não existir"""
    conn = get_db_connection()
    if not conn:
        return False
        
    try:
        cur = conn.cursor()
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
        cur.close()
        print("✅ Tabela 'tarefas' criada/verificada")
        return True
    except Exception as e:
        print(f"❌ Erro ao criar tabela: {e}")
        return False
    finally:
        conn.close()

@app.route('/')
def index():
    """Página principal"""
    conn = get_db_connection()
    if not conn:
        # Se não conectar ao banco, mostra página sem tarefas
        return render_template('index.html', tarefas=[])
    
    try:
        cur = conn.cursor()
        cur.execute('SELECT * FROM tarefas ORDER BY data_criacao DESC')
        tarefas = cur.fetchall()
        cur.close()
        
        # Converter para dicionários
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
        print(f"Erro ao buscar tarefas: {e}")
        return render_template('index.html', tarefas=[])
    finally:
        conn.close()

@app.route('/adicionar', methods=['POST'])
def adicionar_tarefa():
    """Adiciona nova tarefa"""
    titulo = request.form.get('titulo', '').strip()
    if not titulo:
        return redirect('/')
    
    conn = get_db_connection()
    if not conn:
        return redirect('/')
    
    try:
        descricao = request.form.get('descricao', '').strip()
        cur = conn.cursor()
        cur.execute(
            'INSERT INTO tarefas (titulo, descricao) VALUES (%s, %s)',
            (titulo, descricao)
        )
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Erro ao adicionar: {e}")
    finally:
        conn.close()
    
    return redirect('/')

@app.route('/concluir/<int:tarefa_id>')
def concluir_tarefa(tarefa_id):
    """Marca tarefa como concluída"""
    conn = get_db_connection()
    if not conn:
        return redirect('/')
    
    try:
        cur = conn.cursor()
        cur.execute(
            'UPDATE tarefas SET concluida = TRUE WHERE id = %s',
            (tarefa_id,)
        )
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Erro ao concluir: {e}")
    finally:
        conn.close()
    
    return redirect('/')

@app.route('/excluir/<int:tarefa_id>')
def excluir_tarefa(tarefa_id):
    """Exclui tarefa"""
    conn = get_db_connection()
    if not conn:
        return redirect('/')
    
    try:
        cur = conn.cursor()
        cur.execute('DELETE FROM tarefas WHERE id = %s', (tarefa_id,))
        conn.commit()
        cur.close()
    except Exception as e:
        print(f"Erro ao excluir: {e}")
    finally:
        conn.close()
    
    return redirect('/')

@app.route('/health')
def health_check():
    """Health check para o Render"""
    conn = get_db_connection()
    db_status = "connected" if conn else "disconnected"
    if conn:
        conn.close()
    
    return jsonify({
        'status': 'ok',
        'database': db_status,
        'timestamp': datetime.now().isoformat()
    })

# Inicialização
if __name__ == '__main__':
    # Tentar criar tabela ao iniciar
    init_db()
    
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)