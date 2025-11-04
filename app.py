import os
import sqlite3
from flask import Flask, render_template, request, redirect, url_for, jsonify
from datetime import datetime

app = Flask(__name__)

# Configuração do banco
def get_db_connection():
    """Conecta ao SQLite"""
    conn = sqlite3.connect('tarefas.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Inicializa o banco de dados"""
    conn = get_db_connection()
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
    conn.close()
    print("✅ Banco de dados SQLite inicializado")

@app.route('/')
def index():
    """Página principal"""
    conn = get_db_connection()
    tarefas = conn.execute(
        'SELECT * FROM tarefas ORDER BY data_criacao DESC'
    ).fetchall()
    conn.close()
    
    return render_template('index.html', tarefas=tarefas)

@app.route('/adicionar', methods=['POST'])
def adicionar_tarefa():
    """Adiciona nova tarefa"""
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

@app.route('/concluir/<int:tarefa_id>')
def concluir_tarefa(tarefa_id):
    """Marca tarefa como concluída"""
    conn = get_db_connection()
    conn.execute(
        'UPDATE tarefas SET concluida = TRUE WHERE id = ?',
        (tarefa_id,)
    )
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/excluir/<int:tarefa_id>')
def excluir_tarefa(tarefa_id):
    """Exclui tarefa"""
    conn = get_db_connection()
    conn.execute('DELETE FROM tarefas WHERE id = ?', (tarefa_id,))
    conn.commit()
    conn.close()
    return redirect('/')

@app.route('/health')
def health_check():
    """Health check"""
    return jsonify({
        'status': 'ok', 
        'database': 'sqlite',
        'timestamp': datetime.now().isoformat()
    })

# Inicialização
if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)