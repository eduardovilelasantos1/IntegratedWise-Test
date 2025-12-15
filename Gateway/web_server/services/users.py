# web_server/services/users.py

import os
import json
import bcrypt

from web_server.logging_config import setup_logger

logger = setup_logger(__name__)

USERS_FILE = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "users.json")
)


def _write_users(users: dict) -> None:
    """Grava o arquivo users.json com segurança."""
    try:
        with open(USERS_FILE, "w", encoding="utf-8") as f:
            json.dump(users, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        logger.info("Arquivo users.json salvo com sucesso")

    except Exception:
        logger.exception("Erro ao salvar users.json")


def load_users() -> dict:
    """
    Carrega usuários.
    Se não existir, cria admin/admin automaticamente.
    """
    if not os.path.exists(USERS_FILE):
        logger.warning("users.json não encontrado — criando usuário admin padrão")

        hashed = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")
        users = {
            "admin": {
                "password": hashed
            }
        }
        _write_users(users)
        return users

    try:
        with open(USERS_FILE, "r", encoding="utf-8") as f:
            users = json.load(f)

        logger.debug("users.json carregado com sucesso")
        return users

    except json.JSONDecodeError:
        logger.error("users.json corrompido — recriando admin/admin")

        hashed = bcrypt.hashpw(b"admin", bcrypt.gensalt()).decode("utf-8")
        users = {
            "admin": {
                "password": hashed
            }
        }
        _write_users(users)
        return users

    except Exception:
        logger.exception("Erro inesperado ao carregar users.json")
        return {}


def save_users(users: dict) -> None:
    """Interface pública para salvar usuários."""
    logger.debug("Salvando usuários")
    _write_users(users)


def check_password(users: dict, username: str, password: str) -> bool:
    """
    Valida senha do usuário.
    """
    try:
        hashed = users[username]["password"].encode("utf-8")
        result = bcrypt.checkpw(password.encode("utf-8"), hashed)

        logger.info(
            "Tentativa de login para usuário '%s' — %s",
            username,
            "SUCESSO" if result else "FALHA"
        )

        return result

    except KeyError:
        logger.warning("Usuário inexistente: %s", username)
        return False

    except Exception:
        logger.exception("Erro ao validar senha para usuário: %s", username)
        return False


def set_password(users: dict, username: str, new_password: str) -> None:
    """
    Altera senha de um usuário.
    """
    try:
        hashed = bcrypt.hashpw(
            new_password.encode("utf-8"),
            bcrypt.gensalt()
        ).decode("utf-8")

        users[username]["password"] = hashed
        _write_users(users)

        logger.info("Senha alterada com sucesso para usuário: %s", username)

    except Exception:
        logger.exception("Erro ao alterar senha do usuário: %s", username)
