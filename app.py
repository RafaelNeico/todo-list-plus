from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///todos.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# Modelo da Tarefa
class Tarefa(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    descricao = db.Column(db.String(200), nullable=False)
    categoria = db.Column(db.String(50), default='Geral')
    prazo = db.Column(db.String(20))
    concluida = db.Column(db.Boolean, default=False)
    data_criacao = db.Column(db.DateTime, default=datetime.utcnow)

# Criar banco de dados
with app.app_context():
    db.create_all()

# Rotas
@app.route('/')
def index():
    tarefas = Tarefa.query.order_by(Tarefa.data_criacao.desc()).all()
    return render_template('index.html', tarefas=tarefas)

@app.route('/adicionar', methods=['POST'])
def adicionar():
    descricao = request.form['descricao']
    categoria = request.form['categoria'] or 'Geral'
    prazo = request.form['prazo']
    
    nova_tarefa = Tarefa(descricao=descricao, categoria=categoria, prazo=prazo)
    db.session.add(nova_tarefa)
    db.session.commit()
    
    return redirect(url_for('index'))

@app.route('/concluir/<int:id>')
def concluir(id):
    tarefa = Tarefa.query.get_or_404(id)
    tarefa.concluida = not tarefa.concluida
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/excluir/<int:id>')
def excluir(id):
    tarefa = Tarefa.query.get_or_404(id)
    db.session.delete(tarefa)
    db.session.commit()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)