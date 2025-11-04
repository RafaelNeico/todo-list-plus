import os
import psycopg2
from flask import Flask, render_template, request, redirect
import requests

app = Flask(__name__)

def get_db_connection():
    """Conecta ao PostgreSQL no Render com debug"""
    database_url = os.environ.get('DATABASE_URL')
    
    print("=" * 50)
    print("🔍 DEBUG DATABASE CONNECTION")
    print(f"DATABASE_URL exists: {bool(database_url)}")
    if database_url:
        print(f"URL starts with: {database_url[:50]}...")
    
    if database_url:
        try:
            # Conecta ao PostgreSQL
            conn = psycopg2.connect(database_url, sslmode='require')
            
            # Testa a conexão
            cursor = conn.cursor()
            cursor.execute("SELECT version();")
            db_version = cursor.fetchone()
            print(f"✅ PostgreSQL connected: {db_version[0]}")
            cursor.close()
            
            return conn
        except Exception as e:
            print(f"❌ PostgreSQL connection failed: {e}")
            print("🔄 Falling back to SQLite...")
            return get_sqlite_connection()
    else:
        print("ℹ️  No DATABASE_URL, using SQLite")
        return get_sqlite_connection()

def get_sqlite_connection():
    """Fallback para SQLite"""
    import sqlite3
    # No Render, usa /tmp para persistência
    db_path = '/tmp/tarefas.db' if os.environ.get('RENDER') else 'tarefas.db'
    print(f"📁 SQLite path: {db_path}")
    
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """Cria tabelas se não existirem"""
    print("🔄 Initializing database...")
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Detecta se é PostgreSQL
    is_postgres = os.environ.get('DATABASE_URL')
    print(f"📊 Database type: {'PostgreSQL' if is_postgres else 'SQLite'}")
    
    if is_postgres:
        # PostgreSQL
        cursor.execute('''
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
        print("✅ PostgreSQL table created/verified")
    else:
        # SQLite
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS tarefas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                descricao TEXT NOT NULL,
                categoria TEXT DEFAULT 'Geral',
                prioridade TEXT DEFAULT 'Média',
                prazo TEXT,
                concluida BOOLEAN DEFAULT 0,
                data_criacao TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        print("✅ SQLite table created/verified")
    
    conn.commit()
    
    # Conta tarefas existentes
    cursor.execute("SELECT COUNT(*) FROM tarefas")
    count = cursor.fetchone()[0]
    print(f"📈 Total tasks in database: {count}")
    
    conn.close()
    print("✅ Database initialization complete")

@app.route('/')
def index():
    try:
        print("\n🌐 HOME PAGE REQUEST")
        init_db()
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM tarefas ORDER BY id DESC')
        tarefas_data = cursor.fetchall()
        
        print(f"📋 Tasks fetched: {len(tarefas_data)}")
        
        # Converter para formato padrão
        tarefas = []
        for tarefa in tarefas_data:
            tarefas.append({
                'id': tarefa[0],
                'descricao': tarefa[1],
                'categoria': tarefa[2],
                'prioridade': tarefa[3],
                'prazo': tarefa[4],
                'concluida': tarefa[5]
            })
        
        conn.close()
        
        weather = get_weather_data()
        return render_template('index.html', tarefas=tarefas, weather=weather)
        
    except Exception as e:
        print(f"❌ Error in index: {e}")
        return render_template('index.html', tarefas=[], weather=None)

@app.route('/add', methods=['POST'])
def add_task():
    try:
        descricao = request.form['descricao']
        categoria = request.form.get('categoria', 'Geral')
        prioridade = request.form.get('prioridade', 'Média')
        prazo = request.form.get('prazo', '')
        
        print(f"\n➕ ADDING TASK: {descricao}")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('DATABASE_URL'):
            # PostgreSQL
            cursor.execute(
                'INSERT INTO tarefas (descricao, categoria, prioridade, prazo) VALUES (%s, %s, %s, %s) RETURNING id',
                (descricao, categoria, prioridade, prazo)
            )
            task_id = cursor.fetchone()[0]
            print(f"✅ Task added to PostgreSQL with ID: {task_id}")
        else:
            # SQLite
            cursor.execute(
                'INSERT INTO tarefas (descricao, categoria, prioridade, prazo) VALUES (?, ?, ?, ?)',
                (descricao, categoria, prioridade, prazo)
            )
            task_id = cursor.lastrowid
            print(f"✅ Task added to SQLite with ID: {task_id}")
        
        conn.commit()
        conn.close()
        return redirect('/')
        
    except Exception as e:
        print(f"❌ Error adding task: {e}")
        return f"Erro ao adicionar: {str(e)}", 500

@app.route('/concluir/<int:tarefa_id>')
def concluir_tarefa(tarefa_id):
    try:
        print(f"✅ COMPLETING TASK: {tarefa_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('DATABASE_URL'):
            cursor.execute('UPDATE tarefas SET concluida = TRUE WHERE id = %s', (tarefa_id,))
        else:
            cursor.execute('UPDATE tarefas SET concluida = 1 WHERE id = ?', (tarefa_id,))
        
        conn.commit()
        conn.close()
        print(f"✅ Task {tarefa_id} completed")
        return redirect('/')
    except Exception as e:
        print(f"❌ Error completing task: {e}")
        return f"Erro ao concluir tarefa: {str(e)}", 500

@app.route('/reabrir/<int:tarefa_id>')
def reabrir_tarefa(tarefa_id):
    try:
        print(f"🔄 REOPENING TASK: {tarefa_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('DATABASE_URL'):
            cursor.execute('UPDATE tarefas SET concluida = FALSE WHERE id = %s', (tarefa_id,))
        else:
            cursor.execute('UPDATE tarefas SET concluida = 0 WHERE id = ?', (tarefa_id,))
        
        conn.commit()
        conn.close()
        print(f"✅ Task {tarefa_id} reopened")
        return redirect('/')
    except Exception as e:
        print(f"❌ Error reopening task: {e}")
        return f"Erro ao reabrir tarefa: {str(e)}", 500

@app.route('/excluir/<int:tarefa_id>')
def excluir_tarefa(tarefa_id):
    try:
        print(f"🗑️ DELETING TASK: {tarefa_id}")
        conn = get_db_connection()
        cursor = conn.cursor()
        
        if os.environ.get('DATABASE_URL'):
            cursor.execute('DELETE FROM tarefas WHERE id = %s', (tarefa_id,))
        else:
            cursor.execute('DELETE FROM tarefas WHERE id = ?', (tarefa_id,))
        
        conn.commit()
        conn.close()
        print(f"✅ Task {tarefa_id} deleted")
        return redirect('/')
    except Exception as e:
        print(f"❌ Error deleting task: {e}")
        return f"Erro ao excluir tarefa: {str(e)}", 500

def get_weather_data(city='São Paulo'):
    """Sua função existente do clima"""
    try:
        api_key = os.environ.get('OPENWEATHER_API_KEY', 'sua_chave_aqui')
        if not api_key or api_key == 'sua_chave_aqui':
            return None
            
        url = f"http://api.openweathermap.org/data/2.5/weather?q={city}&appid={api_key}&units=metric&lang=pt_br"
        response = requests.get(url)
        
        if response.status_code == 200:
            data = response.json()
            return {
                'cidade': data['name'],
                'temperatura': round(data['main']['temp']),
                'descricao': data['weather'][0]['description'].title(),
                'icone': data['weather'][0]['icon'],
                'sensacao': round(data['main']['feels_like'])
            }
        return None
    except Exception as e:
        print(f"❌ Weather API error: {e}")
        return None

if __name__ == '__main__':
    print("🚀 Starting Flask application...")
    init_db()
    port = int(os.environ.get('PORT', 5000))
    print(f"🌐 Server running on port {port}")
    app.run(host='0.0.0.0', port=port)