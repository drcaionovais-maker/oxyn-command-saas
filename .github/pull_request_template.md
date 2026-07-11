## Resumo

<!-- O que essa PR muda e por quê, em 1-3 frases. -->

## Como foi testado

<!-- Comandos rodados, cenários exercitados. Ex: pytest -q, curl manual num endpoint. -->

## Checklist

- [ ] `./.venv/bin/pytest -q` passa localmente
- [ ] `./.venv/bin/ruff check .` sem erros
- [ ] Se `app/models.py` mudou: gerei uma migração (`alembic revision --autogenerate -m "..."`) e testei `alembic upgrade head` / `downgrade`
- [ ] Se um endpoint ou comportamento existente mudou: atualizei o `README.md`
- [ ] Mensagens de erro/detail voltadas ao usuário estão em português, como o resto da API
