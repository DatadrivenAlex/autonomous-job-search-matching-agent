FROM python:3.13-slim
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1
WORKDIR /app
COPY pyproject.toml README.md ./
COPY jobmatch ./jobmatch
RUN pip install --no-cache-dir 'playwright>=1.55,<2' && playwright install --with-deps chromium
COPY examples ./examples
ENTRYPOINT ["python", "-m", "jobmatch"]
CMD ["examples/jobs.html", "--profile", "examples/profile.json"]
