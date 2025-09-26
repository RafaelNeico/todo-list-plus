import requests
import os

from flask import Flask, render_template, request, redirect
import sqlite3

app = Flask(__name__)

def get_db():
    conn = sqlite3.connect('tarefas.db')
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db()
    conn.execute('''
        CREATE TABLE IF NOT EXISTS tarefas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            descricao TEXT NOT NULL,
            categoria TEXT DEFAULT 'Geral',
            prazo TEXT,
            concluida BOOLEAN DEFAULT 0,
            data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

def obter_clima(cidade="Sao Paulo"):
    """Obtém dados do clima para uma cidade"""
    try:
        # SUA CHAVE API AQUI - substitua pela chave real
        api_key = "00242a4366f2f684e8f901da0d365d44"  
        url = f"http://api.openweathermap.org/data/2.5/weather?q={cidade}&appid={api_key}&units=metric&lang=pt_br"
        
        print("Debug: Tentando obter clima para:", cidade)
        print("Debug: URL da API:", url)
        
        response = requests.get(url)
        print("Debug: Status code:", response.status_code)
        
        if response.status_code == 200:
            dados = response.json()
            print("Debug: Dados do clima obtidos com sucesso!")
            
            return {
                'cidade': dados['name'],
                'temperatura': dados['main']['temp'],
                'descricao': dados['weather'][0]['description'],
                'icone': dados['weather'][0]['icon'],
                'sensacao': dados['main']['feels_like'],
                'umidade': dados['main']['humidity']
            }
        else:
            print("Debug: Erro API:", response.status_code, "-", response.text)
            return None
    except Exception as e:
        print("Debug: Erro ao obter clima:", str(e))
        return None
    
@app.route('/')
def index():
    init_db()
    conn = get_db()
    tarefas = conn.execute('SELECT * FROM tarefas ORDER BY data_criacao DESC').fetchall()
    conn.close()
    
    # Obter dados do clima
    clima = obter_clima()
    print("Debug: Clima retornado:", clima)
    
    return render_template('index.html', tarefas=tarefas, clima=clima)

@app.route('/add', methods=['POST'])
def add_task():
    descricao = request.form['descricao']
    categoria = request.form.get('categoria', 'Geral')
    prazo = request.form.get('prazo', '')
    
    conn = get_db()
    conn.execute('INSERT INTO tarefas (descricao, categoria, prazo) VALUES (?, ?, ?)',
                 (descricao, categoria, prazo))
    conn.commit()
    conn.close()
    
    return redirect('/')

@app.route('/complete/<int:task_id>')
def complete_task(task_id):
    conn = get_db()
    task = conn.execute('SELECT * FROM tarefas WHERE id = ?', (task_id,)).fetchone()
    if task:
        new_status = 0 if task['concluida'] else 1
        conn.execute('UPDATE tarefas SET concluida = ? WHERE id = ?', (new_status, task_id))
        conn.commit()
    conn.close()
    return redirect('/')

@app.route('/delete/<int:task_id>')
def delete_task(task_id):
    conn = get_db()
    conn.execute('DELETE FROM tarefas WHERE id = ?', (task_id,))
    conn.commit()
    conn.close()
    return redirect('/')

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
