def test_health_check_does_not_require_database_or_authentication(tmp_path):
    from app import create_app

    class TestConfig:
        SECRET_KEY = 'test-secret'
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / 'uploads')

    app = create_app(TestConfig)
    response = app.test_client().get('/health')

    assert response.status_code == 200
    assert response.get_json() == {'status': 'ok'}
    assert (tmp_path / 'uploads').is_dir()


def test_root_still_redirects_to_login_for_unauthenticated_users(tmp_path):
    from app import create_app

    class TestConfig:
        SECRET_KEY = 'test-secret'
        SQLALCHEMY_DATABASE_URI = 'sqlite:///:memory:'
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        UPLOAD_FOLDER = str(tmp_path / 'uploads')

    response = create_app(TestConfig).test_client().get('/')

    assert response.status_code == 302
    assert response.headers['Location'].startswith('/login')
