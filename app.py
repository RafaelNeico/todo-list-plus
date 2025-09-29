from flask import Flask, render_template, request, redirect, url_for, g
import sqlite3
import os
import requests

app = Flask(__name__)
DATABASE = 'tarefas.db'

# Configuração da API do OpenWeather - usando variável de ambiente
OPENWEATHER_API_KEY = os.environ.get('OPENWEATHER_API_KEY', '00242a4366f2f684e8f901da0d365d44')
OPENWEATHER_BASE_URL = 'http://api.openweathermap.org/data/2.5/weather'

def get_db():
    if not hasattr(g, '_database'):
        g._database = sqlite3.connect(DATABASE)
        g._database.row_factory = sqlite3.Row
    return g._database

@app.teardown_appcontext
def close_connection(exception):
    if hasattr(g, '_database'):
        g._database.close()

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('''
            CREATE TABLE IF NOT EXISTS tariffs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                categoria TEXT,
                prioridade TEXT,
                prazo TEXT,
                concluida BOOLEAN DEFAULT 0
            )
        ''')
        db.commit()

def get_weather_data(city='São Paulo'):
    """
    Obtém dados do clima para uma cidade específica
    """
    if OPENWEATHER_API_KEY == 'sua_chave_aqui' or not OPENWEATHER_API_KEY:
        return None
        
    try:
        params = {
            'q': city,
            'appid': OPENWEATHER_API_KEY,
            'units': 'metric',  # Para temperatura em Celsius
            'lang': 'pt_br'     # Para descrições em português
        }
        
        response = requests.get(OPENWEATHER_BASE_URL, params=params, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'cidade': data['name'],
                'temperatura': round(data['main']['temp']),
                'descricao': data['weather'][0]['description'].title(),
                'icone': data['weather'][0]['icon'],
                'humidade': data['main']['humidity'],
                'vento': round(data['wind']['speed'] * 3.6),  # Converte m/s para km/h
                'sensacao': round(data['main']['feels_like'])
            }
        else:
            print(f"Erro na API do clima: {response.status_code}")
            return None
            
    except Exception as e:
        print(f"Erro ao buscar dados do clima: {e}")
        return None

# Rota principal
@app.route('/')
def index():
    try:
        db = get_db()
        cursor = db.execute('SELECT * FROM tariffs ORDER BY id DESC')
        tarefas = cursor.fetchall()
        
        lista_tarefas = []
        for tarefa in tarefas:
            lista_tarefas.append({
                'id': tarefa['id'],
                'descricao': tarefa['descricao'],
                'categoria': tarefa['categoria'],
                'prioridade': tarefa['prioridade'],
                'prazo': tarefa['prazo'],
                'concluida': tarefa['concluida']
            })
        
        # Obter dados do clima
        weather_data = get_weather_data()
        
        return render_template('index.html', 
                             tarefas=lista_tarefas, 
                             weather=weather_data)
                             
    except Exception as e:
        print("Erro ao carregar tarefas:", e)
        return render_template('index.html', tarefas=[], weather=None)

@app.route('/add', methods=['POST'])
def add_task():
    try:
        descricao = request.form['descricao']
        categoria = request.form.get('categoria', 'Geral')
        prioridade = request.form.get('prioridade', 'Média')
        prazo = request.form.get('prazo', '')
        
        db = get_db()
        db.execute('INSERT INTO tariffs (descricao, categoria, prioridade, prazo) VALUES (?, ?, ?, ?)',
                  (descricao, categoria, prioridade, prazo))
        db.commit()
        
        return redirect('/')
    except Exception as e:
        return f"Erro ao adicionar tarefa: {str(e)}", 500

@app.route('/concluir/<int:tarefa_id>')
def concluir_tarefa(tarefa_id):
    try:
        db = get_db()
        db.execute('UPDATE tariffs SET concluida = 1 WHERE id = ?', (tarefa_id,))
        db.commit()
        return redirect('/')
    except Exception as e:
        return f"Erro ao concluir tarefa: {str(e)}", 500

@app.route('/reabrir/<int:tarefa_id>')
def reabrir_tarefa(tarefa_id):
    try:
        db = get_db()
        db.execute('UPDATE tariffs SET concluida = 0 WHERE id = ?', (tarefa_id,))
        db.commit()
        return redirect('/')
    except Exception as e:
        return f"Erro ao reabrir tarefa: {str(e)}", 500

@app.route('/excluir/<int:tarefa_id>')
def excluir_tarefa(tarefa_id):
    try:
        db = get_db()
        db.execute('DELETE FROM tariffs WHERE id = ?', (tarefa_id,))
        db.commit()
        return redirect('/')
    except Exception as e:
        return f"Erro ao excluir tarefa: {str(e)}", 500

@app.route('/limpar_concluidas')
def limpar_concluidas():
    try:
        db = get_db()
        db.execute('DELETE FROM tariffs WHERE concluida = 1')
        db.commit()
        return redirect('/')
    except Exception as e:
        return f"Erro ao limpar tarefas concluidas: {str(e)}", 500

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        print("Criando novo banco de dados...")
        init_db()
    else:
        print("Banco de dados ja existe.")
    
    # Configuração para produção - usar porta do Render
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=False, host='0.0.0.0', port=port)