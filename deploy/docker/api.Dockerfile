ARG PYTHON_IMAGE
FROM ${PYTHON_IMAGE} AS foundation
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 \
    V2_APP_ENVIRONMENT=production V2_DATA_MODE=verified \
    V2_MODEL_MODE=disabled DEMO_MODE=false
WORKDIR /app
COPY requirements.txt /app/requirements.txt
RUN python -m pip install --no-cache-dir --require-hashes -r requirements.txt \
    && groupadd --gid 10001 study \
    && useradd --uid 10001 --gid study --no-create-home study
# The runtime does not contain the v1 application, seed or private service assembly.
COPY services/api/__init__.py /app/services/api/__init__.py
COPY services/api/app/__init__.py services/api/app/settings.py /app/services/api/app/
COPY services/api/app/api/__init__.py services/api/app/api/public.py services/api/app/api/catalog_access.py /app/services/api/app/api/
COPY services/api/app/api/v2/__init__.py services/api/app/api/v2/router.py services/api/app/api/v2/errors.py services/api/app/api/v2/schemas.py /app/services/api/app/api/v2/
USER 10001:10001
EXPOSE 8000
CMD ["python", "-m", "uvicorn", "services.api.app.api.public:create_public_app", "--factory", "--host", "0.0.0.0", "--port", "8000", "--no-proxy-headers", "--no-access-log", "--log-level", "warning"]

FROM foundation AS maintenance
USER root
COPY services/api /app/services/api
COPY deploy/__init__.py deploy/migrate.py /app/deploy/
USER 10001:10001
ENTRYPOINT ["python", "-m", "deploy.migrate"]
CMD ["--help"]
