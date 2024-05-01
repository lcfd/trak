rm dist.tar.gz
tar --exclude=".venv" --exclude="dist" --exclude=".mypy_cache" --exclude=".pytest_cache" --exclude="**/__pycache__" -czvf dist.tar.gz cli
