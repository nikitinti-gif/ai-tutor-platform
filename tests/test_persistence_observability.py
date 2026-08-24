from unittest.mock import patch

from bot import ege_persistence_report


def test_postgres_ege_persistence_is_durable():
    with patch.dict("os.environ", {"DATABASE_URL": "postgresql://example/db"}, clear=True):
        assert ege_persistence_report() == {"backend": "postgres", "durable": True}


def test_json_ege_persistence_warns_about_render_data_loss():
    with patch.dict("os.environ", {}, clear=True):
        assert ege_persistence_report() == {
            "backend": "json",
            "durable": False,
            "warning": "Render restart/deploy may lose student exam state",
        }
