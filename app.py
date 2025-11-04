import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuração do banco
def get_db_connection():
    """Conecta ao SQLite e garante que a tabela existe"""
    conn = sqlite3.connect('tarefas.db')
    conn.row_factory = sqlite3.Row
    
    # Garantir que a tabela existe
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descricao TEXT,
            concluida BOOLEAN DEFAULT FALSE,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    
    return conn

def init_db():
    """Inicializa o banco de dados (usado apenas uma vez)"""
    try:
        conn = get_db_connection()
        print("✅ Banco de dados inicializado com sucesso")
        conn.close()
        return True
    except Exception as e:
        print(f"❌ Erro ao inicializar banco: {e}")
        return False

@app.route('/')
def index():
    """Página principal"""
    try:
        conn = get_db_connection()
        tarefas = conn.execute(
            'SELECT * FROM tarefas ORDER BY data_criacao DESC'
        ).fetchall()
        conn.close()
        
        return render_template('index.html', tarefas=tarefas)
    except Exception as e:
        print(f"Erro ao carregar tarefas: {e}")
        return render_template('index.html', tarefas=[])

@app.route('/adicionar', methods=['POST'])
def adicionar_tarefa():
    """Adiciona nova tarefa"""
    try:
        titulo = request.form.get('titulo', '').strip()
        descricao = request.form.get('descricao', '').strip()
        
        if titulo:
            conn = get_db_connection()
            conn.execute(
                'INSERT INTO tarefas (titulo, descricao) VALUES (?, ?)',
                (titulo, descricao)
            )
            conn.commit()
            conn.close()
        
        return redirect('/')
    except Exception as e:
        print(f"Erro ao adicionar tarefa: {e}")
        return redirect('/')

@app.route('/concluir/<int:tarefa_id>')
def concluir_tarefa(tarefa_id):
    """Marca tarefa como concluída"""
    try:
        conn = get_db_connection()
        conn.execute(
            'UPDATE tarefas SET concluida = TRUE WHERE id = ?',
            (tarefa_id,)
        )
        conn.commit()
        conn.close()
        return redirect('/')
    except Exception as e:
        print(f"Erro ao concluir tarefa: {e}")
        return redirect('/')

@app.route('/excluir/<int:tarefa_id>')
def excluir_tarefa(tarefa_id):
    """Exclui tarefa"""
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM tarefas WHERE id = ?', (tarefa_id,))
        conn.commit()
        conn.close()
        return redirect('/')
    except Exception as e:
        print(f"Erro ao excluir tarefa: {e}")
        return redirect('/')

@app.route('/health')
def health_check():
    """Health check"""
    try:
        conn = get_db_connection()
        count = conn.execute('SELECT COUNT(*) as count FROM tarefas').fetchone()['count']
        conn.close()
        
        return jsonify({
            'status': 'ok', 
            'database': 'sqlite',
            'tarefas_count': count,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({
            'status': 'error',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@app.route('/reset-db')
def reset_db():
    """Rota para resetar o banco (apenas para desenvolvimento)"""
    try:
        conn = get_db_connection()
        conn.execute('DROP TABLE IF EXISTS tarefas')
        conn.execute('''
            CREATE TABLE tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                titulo TEXT NOT NULL,
                descricao TEXT,
                concluida BOOLEAN DEFAULT FALSE,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        conn.commit()
        conn.close()
        return jsonify({'status': 'banco resetado'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Inicialização do app
if __name__ == '__main__':
    # Inicializar banco quando o app iniciar
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
else:
    # Inicializar banco quando rodando com Gunicorn
    init_db()