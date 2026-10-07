FROM ghcr.io/open-webui/open-webui:v0.11.4@sha256:332438e079ad23bb11b0ab278b43e7c98b50e8cec14b0840281644e8a289f49f
COPY code/storage/provider.py /app/backend/open_webui/storage/provider.py
COPY code/routers/files.py /app/backend/open_webui/routers/files.py
RUN rm -rf /app/build
COPY build/ /app/build/
RUN python -c "import ast,pathlib; [ast.parse(pathlib.Path('/app/backend/open_webui/'+p).read_text()) for p in ['storage/provider.py','routers/files.py']]"
LABEL corp.issue="474" corp.upstream.commit="8bd8b4fac5e059578ac0c74b3c18d11139f88b7d" corp.patch.sha256="e7d4be27abbfe57ef970f1074a3f861b9ebac74d44eaee39a9515bf765a236df"
