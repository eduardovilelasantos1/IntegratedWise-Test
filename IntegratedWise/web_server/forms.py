from flask_wtf import FlaskForm
from wtforms import PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, EqualTo, Length

class FormLogin(FlaskForm):
    password = PasswordField('Senha', validators=[DataRequired(), Length(min=5, max=10)])
    botao_submit_login = SubmitField('Fazer Login')
    remember_me = BooleanField('Lembrar Senha')  # opcional, pode remover se não usar

class FormAlterarSenha(FlaskForm):
    senha_atual = PasswordField('Senha Atual', validators=[DataRequired(), Length(min=5, max=10)])
    nova_senha = PasswordField('Nova Senha', validators=[DataRequired(), Length(min=5, max=10)])
    confirmar_senha = PasswordField('Confirmar Nova Senha', validators=[
        DataRequired(), 
        Length(min=5, max=10), 
        EqualTo('nova_senha', message='As senhas devem ser iguais')
    ])
    
    botao_submit_alterar_senha = SubmitField('Alterar Senha')
