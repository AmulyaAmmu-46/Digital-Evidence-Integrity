from app import create_app
from app.extensions import db
from app.models.case_viewer_grant import CaseViewerGrant
from sqlalchemy import inspect, text


app = create_app()


if __name__ == '__main__':
    with app.app_context():
        CaseViewerGrant.__table__.create(bind=db.engine, checkfirst=True)
        inspector = inspect(db.engine)
        if inspector.has_table('custody_events'):
            custody_columns = {column['name'] for column in inspector.get_columns('custody_events')}
            if 'result' not in custody_columns:
                db.session.execute(text(
                    "ALTER TABLE custody_events ADD COLUMN result VARCHAR(20) NOT NULL DEFAULT 'SUCCESS'"
                ))
                db.session.commit()
        print('RBAC and custody schema upgrades are ready.')