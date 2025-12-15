# web_server/services/json_store.py

import os
import json

from web_server.logging_config import setup_logger

logger = setup_logger(__name__)

BASE_CONFIG_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "configs")
)


def _get_path(filename: str) -> str:
    """Retorna o caminho absoluto do arquivo JSON."""
    return os.path.join(BASE_CONFIG_DIR, filename)


def load_json(filename: str) -> dict:
    """
    Carrega um arquivo JSON da pasta configs.
    Retorna {} se não existir ou se ocorrer erro.
    """
    path = _get_path(filename)
    logger.debug("Carregando JSON: %s", path)

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            logger.debug("JSON carregado com sucesso: %s", filename)
            return data

    except FileNotFoundError:
        logger.warning("Arquivo JSON não encontrado: %s", filename)
        return {}

    except json.JSONDecodeError:
        logger.error("Erro de parsing JSON em: %s", filename)
        return {}

    except Exception:
        logger.exception("Erro inesperado ao carregar JSON: %s", filename)
        return {}


def save_json(filename: str, data: dict) -> None:
    """
    Salva um arquivo JSON na pasta configs.
    Garante flush e fsync para persistência.
    """
    path = _get_path(filename)
    logger.debug("Salvando JSON: %s", path)

    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
            f.flush()
            os.fsync(f.fileno())

        logger.info("JSON salvo com sucesso: %s", filename)

    except Exception:
        logger.exception("Erro ao salvar JSON: %s", filename)
