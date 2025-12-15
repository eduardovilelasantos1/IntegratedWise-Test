# web_server/auth.py

import bcrypt
from flask import (
    Blueprint, render_template, request,
    redirect, url_for, flash, session
)

from web_server.forms import FormLogin, FormAlterarSenha
from web_server.services.users import load_users, save_users
from web_server.logging_config import setup_logger

logger = setup_logger(__name__)

auth_bp = Blueprint("auth", __name__)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    logger.debug("Acessando rota /login")

    form = FormLogin()
    form_pw = FormAlterarSenha()
    users = load_users()

    # ---------------- LOGIN ----------------
    if form.validate_on_submit() and "botao_submit_login" in request.form:
        logger.info("Tentativa de login do usuário admin")

        try:
            if bcrypt.checkpw(
                form.password.data.encode("utf-8"),
                users["admin"]["password"].encode("utf-8")
            ):
                session["logged_in"] = True
                logger.info("Login realizado com sucesso")
                flash("Login ok!", "alert-success")
                return redirect(url_for("routes_config.configuracao"))
            else:
                logger.warning("Falha de login: senha incorreta")
                flash("Senha incorreta.", "alert-danger")
        except Exception as e:
            logger.exception("Erro durante autenticação")
            flash("Erro interno no login.", "alert-danger")

    # ---------------- ALTERAR SENHA ----------------
    if form_pw.validate_on_submit() and "botao_submit_alterar_senha" in request.form:
        logger.info("Solicitação de alteração de senha")

        try:
            if not bcrypt.checkpw(
                form_pw.senha_atual.data.encode("utf-8"),
                users["admin"]["password"].encode("utf-8")
            ):
                logger.warning("Senha atual incorreta ao tentar alterar")
                flash("Senha atual errada.", "alert-danger")

            elif form_pw.nova_senha.data != form_pw.confirmar_senha.data:
                logger.warning("Nova senha e confirmação não conferem")
                flash("Senhas não conferem.", "alert-danger")

            else:
                users["admin"]["password"] = bcrypt.hashpw(
                    form_pw.nova_senha.data.encode("utf-8"),
                    bcrypt.gensalt()
                ).decode("utf-8")

                save_users(users)
                logger.info("Senha alterada com sucesso")
                flash("Senha alterada!", "alert-success")
                return redirect(url_for("auth.login"))

        except Exception as e:
            logger.exception("Erro ao alterar senha")
            flash("Erro ao alterar senha.", "alert-danger")

    return render_template(
        "login.html",
        form_login=form,
        form_alterar_senha=form_pw
    )


@auth_bp.route("/logout")
def logout():
    logger.info("Logout realizado")
    session.pop("logged_in", None)
    return redirect(url_for("auth.login"))
