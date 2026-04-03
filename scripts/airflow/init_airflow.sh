#!/bin/bash
set -euo pipefail

airflow db migrate

python -c "exec(\"import os\\nfrom airflow.www.app import create_app\\nfrom werkzeug.security import generate_password_hash\\napp = create_app()\\nusername = os.environ.get('AIRFLOW_WEB_USER', 'airflow')\\npassword = os.environ.get('AIRFLOW_WEB_PASSWORD', 'airflow')\\nwith app.app_context():\\n    appbuilder = app.appbuilder\\n    sm = appbuilder.sm\\n    session = appbuilder.get_session\\n    role = sm.find_role('Admin')\\n    if role is None:\\n        raise RuntimeError('Admin role not found')\\n    user = sm.find_user(username=username)\\n    if user is None:\\n        user = sm.user_model()\\n        session.add(user)\\n    user.username = username\\n    user.first_name = 'Air'\\n    user.last_name = 'Flow'\\n    user.email = 'airflow@example.com'\\n    user.active = True\\n    user.password = generate_password_hash(password)\\n    user.roles = [role]\\n    session.commit()\")"
