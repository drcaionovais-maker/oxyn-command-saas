# OXYN Command — SaaS Backend

Backend Python multi-tenant para gestão operacional de serviços de anestesiologia. O projeto foi desenhado para conectar o aplicativo mobile OXYN Command a dados reais, com isolamento por empresa, permissões e auditoria.

## O que já está implementado

- Autenticação com access token e refresh token JWT
- Senhas protegidas com Argon2
- Isolamento multi-tenant em todas as entidades operacionais
- Perfis: proprietário, administrador, coordenador, anestesista, enfermagem e visualizador
- Cadastro de hospitais e salas cirúrgicas
- Estado operacional das salas e procedimentos em andamento
- Escalas, check-in e check-out
- Checklist de segurança do paciente
- Alertas operacionais e resolução de ocorrências
- Resumo do painel por hospital
- Trilha de auditoria
- PostgreSQL, Docker Compose, Alembic, testes e documentação OpenAPI

## Início rápido

1. Duplique o arquivo de configuração:

   ```bash
   cp .env.example .env
   ```

2. Troque `SECRET_KEY` e `BOOTSTRAP_ADMIN_PASSWORD` no `.env`.

3. Suba o sistema:

   ```bash
   docker compose up --build
   ```

4. Abra a documentação em `http://localhost:8000/docs`.

O usuário inicial é criado com os valores `BOOTSTRAP_ADMIN_EMAIL` e `BOOTSTRAP_ADMIN_PASSWORD` do `.env`.

## Login

O endpoint `POST /api/v1/auth/login` usa formulário OAuth2:

```bash
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H 'Content-Type: application/x-www-form-urlencoded' \
  -d 'username=admin@oxyn.health&password=ChangeMe123!'
```

Use o `access_token` retornado como `Authorization: Bearer <token>`.

## Rotas principais

| Área | Endpoint |
|---|---|
| Identidade | `/api/v1/auth` |
| Usuários | `/api/v1/users` |
| Hospitais e salas | `/api/v1/hospitals` |
| Escalas e presença | `/api/v1/shifts` |
| Segurança | `/api/v1/safety` |
| Alertas | `/api/v1/alerts` |
| Painel | `/api/v1/dashboard/{hospital_id}` |

## Migrações

Para gerar a primeira migração após subir o banco:

```bash
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```

O `scripts.bootstrap` usa `create_all` para facilitar o primeiro teste. Em produção, utilize exclusivamente migrações Alembic.

## Segurança antes de produção

- Guardar segredos em cofre de credenciais, nunca no repositório
- Executar atrás de HTTPS e proxy reverso
- Restringir CORS ao domínio oficial
- Usar serviço gerenciado de PostgreSQL com backups e criptografia
- Adicionar rate limiting, revogação de sessão e MFA para administradores
- Evitar dados clínicos identificáveis; adotar identificadores pseudonimizados
- Formalizar controles LGPD, política de retenção e resposta a incidentes

## Próxima evolução recomendada

1. Conectar o frontend OXYN Command aos endpoints.
2. Implantar WebSockets/Redis para atualização em tempo real.
3. Criar cobrança recorrente e gestão de planos.
4. Integrar DoctorID, WhatsApp oficial e equipamentos hospitalares.
5. Adicionar relatórios, exportação e painel administrativo da plataforma.
